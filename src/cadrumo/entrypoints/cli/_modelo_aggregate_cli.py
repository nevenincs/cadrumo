"""Behavior handlers for modelo aggregation commands."""

from __future__ import annotations

import json

import typer
from pydantic import BaseModel, ValidationError

from ...application.aggregation.counterpart import CounterpartObservation
from ...application.aggregation.foreign_assets import ForeignAssetIngestObservation
from ...application.aggregation.invoice_retencion import (
    InvoiceWithholdingEvidenceRequest,
)
from ...application.aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from ...application.aggregation.service import PerModeloAggregationCommand, PerModeloAggregationContributor
from ...application.aggregation.withholding_filing_cadence import PERIODIC_WITHHOLDING_MODELOS
from ...application.modelo.aggregate_operation import (
    ModeloAggregateGenerationAudit,
    ModeloAggregateProjection,
    ModeloAggregateWindow,
)
from ...application.modelo.invoice_withholding_capture_operation import ModeloInvoiceWithholdingCaptureProjection
from ...core.aggregation import RetencionClave
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.modelo import Modelo
from ...core.period import Period, PeriodError
from ...domain.modelos.codes import ModeloCode
from ._modelo_behavior_support import resolve_year_period
from ._modelo_payloads import (
    ModeloAggregateResult,
    WithholdingGenerationAuditPayload,
    WithholdingWindowBaselinePayload,
    WithholdingWindowReadbackPayload,
)
from .common import emit_envelope
from .modelo_aux_payloads import WithholdingClaveBreakdownPayload
from .runtime_modelo_aggregate import run_modelo_aggregate
from .runtime_modelo_invoice_withholding import aggregate_modelo_with_received_invoice_retencion

# Modelo 123 is absent on purpose: its capital withholding is evidenced by the
# paying ledger transaction, and invoice evidence for it is refused outright.
_INVOICE_EVIDENCE_MODELOS = frozenset({Modelo("111").value, Modelo("115").value})
_PERIODIC_WINDOW_MODELOS = frozenset(modelo.value for modelo in PERIODIC_WITHHOLDING_MODELOS)
_LEDGER_PAYMENT_WITHHOLDING_MODELOS = frozenset({"111", "123"})


def _invoice_capture_period(year: int, token: str) -> Period:
    """Parse the transport period without consulting ambient registry authority."""
    try:
        return Period.from_year_and_code(year, token.strip())
    except PeriodError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _invoice_capture_aggregate_result(
    projection: ModeloInvoiceWithholdingCaptureProjection,
) -> ModeloAggregateResult:
    """Adapt the worker's bounded aggregate and window fields to the CLI envelope."""
    window = projection.withholding_window
    if (
        projection.provider is not PerModeloAggregationContributor.RETENCIONES
        or projection.observation_count is None
        or projection.source_kinds is None
        or projection.result_row_count is None
        or window is None
    ):
        raise ValueError("captured invoice withholding omitted aggregate summary metadata")
    audit = window.generation_audit
    return ModeloAggregateResult(
        modelo=ModeloCode(projection.modelo),
        period=projection.period.to_period(),
        provider=projection.provider,
        observation_count=projection.observation_count,
        source_kinds=list(projection.source_kinds),
        result_row_count=projection.result_row_count,
        withholding_window=WithholdingWindowReadbackPayload(
            baseline=WithholdingWindowBaselinePayload(
                scope_token=window.baseline.scope_token,
                generation_id=window.baseline.generation_id,
            ),
            generation=window.generation,
            generation_audit=(
                None
                if audit is None
                else WithholdingGenerationAuditPayload(
                    parent_generation_id=audit.parent_generation_id,
                    mode=audit.mode,
                    supersedes_generation_id=audit.supersedes_generation_id,
                )
            ),
        ),
    )


def _aggregate_operation_result(projection: ModeloAggregateProjection) -> ModeloAggregateResult:
    """Adapt the exact-profile operation's allowlisted summary to the CLI envelope."""
    if (
        projection.outcome != "aggregated"
        or projection.provider is None
        or projection.observation_count is None
        or projection.source_kinds is None
        or projection.result_row_count is None
        or projection.clave_breakdown is None
    ):
        raise ValueError("registered modelo aggregate omitted its summary fields")
    window = projection.withholding_window
    _require_aggregate_window(projection, window)
    audit = None if window is None else window.generation_audit
    return ModeloAggregateResult(
        modelo=ModeloCode(projection.modelo),
        period=projection.period.to_period(),
        provider=projection.provider,
        observation_count=projection.observation_count,
        source_kinds=list(projection.source_kinds),
        result_row_count=projection.result_row_count,
        clave_breakdown=[
            WithholdingClaveBreakdownPayload(
                clave=RetencionClave.from_registry(row.clave),
                percepcion_count=row.percepcion_count,
                percibido_total=row.percibido_total.decimal,
                retencion_total=row.retencion_total.decimal,
            )
            for row in projection.clave_breakdown
        ],
        withholding_window=_aggregate_window_payload(window, audit),
    )


def _calculation_rows_absent_notices(projection: ModeloAggregateProjection) -> list[Notice]:
    """Warn once for each source the calculation reads that holds no stored row.

    An empty summary then reads as missing data rather than as a proven zero;
    a stored row whose amounts are zero is counted and raises no warning.
    """
    period = projection.period.to_period()
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="modelo.aggregate.calculation_rows_absent",
            message=tr(
                "cli.app.modelo.aggregate.calculation_rows_absent",
                modelo=projection.modelo,
                filing_year=period.filing_year,
                period=period.registry_token,
                source_family=source_family.value,
            ),
            context={
                "modelo": projection.modelo,
                "filing_year": str(period.filing_year),
                "period": period.registry_token,
                "revision": projection.calculation_revision_id or "",
                "source_family": source_family.value,
                "reason": "stored_rows_absent",
            },
        )
        for source_family in projection.absent_source_families or ()
    ]


def _refuse_misplaced_ledger_payment_withholding(
    modelo: str,
    *,
    ledger_payment_withholding: list[str] | None,
    received_invoice_retencion: list[str] | None,
    counterpart_observation: list[str] | None,
    foreign_asset_observation: list[str] | None,
) -> None:
    """Refuse a ledger-payment capture outside its supported, exclusive input route.

    One command writes one allocation from one evidence route; letting a
    payment capture share a command with another evidence provider would make
    its reported window depend on which input landed first.
    """
    if not ledger_payment_withholding:
        return
    if modelo not in _LEDGER_PAYMENT_WITHHOLDING_MODELOS:
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.ledger_payment_withholding_wrong_modelo", modelo=modelo))
    if any(
        (
            received_invoice_retencion,
            counterpart_observation,
            foreign_asset_observation,
        )
    ):
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.ledger_payment_withholding_exclusive"))
    if len(ledger_payment_withholding) > 1:
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.ledger_payment_withholding_single_allocation"))


def _aggregate_output_lines(
    result: ModeloAggregateResult,
    *,
    notices: list[Notice],
) -> list[str]:
    """Render the text envelope lines for one per-modelo aggregation."""
    source_kinds = ", ".join(source_kind.value for source_kind in result.source_kinds) or "-"
    lines = [
        "operation\tmodelo.aggregate",
        f"modelo\t{result.modelo}",
        f"period\t{result.period.registry_token}",
        f"provider\t{result.provider.value}",
        f"observation_count\t{result.observation_count}",
        f"source_kinds\t{source_kinds}",
        f"result_row_count\t{result.result_row_count}",
    ]
    if result.clave_breakdown:
        lines.append("clave\tpercepcion_count\tpercibido_total\tretencion_total")
        lines.extend(
            f"clave_breakdown\t{row.clave.value}\t{row.percepcion_count}\t{row.percibido_total}\t{row.retencion_total}"
            for row in result.clave_breakdown
        )
    lines.extend(notice.message for notice in notices)
    return lines


def _parse_typed_cli_observations[ObservationT: BaseModel](
    values: list[str] | None, *, model: type[ObservationT], flag: str
) -> tuple[ObservationT, ...]:
    """Parse raw JSON observation objects into typed application records."""
    parsed: list[ObservationT] = []
    for raw in values or ():
        try:
            top = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_parse_error", flag=flag, pos=exc.pos)) from exc
        if not isinstance(top, dict):
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_not_object", flag=flag))
        try:
            parsed.append(model.model_validate_json(raw))
        except ValidationError as exc:
            details = "; ".join(f"{'.'.join(str(s) for s in e['loc'])}: {e['msg']}" for e in exc.errors())
            raise typer.BadParameter(
                tr("cli.app.modelo.aggregate.json_validation_error", flag=flag, details=details)
            ) from exc
    return tuple(parsed)


__all__ = ["aggregate_modelo"]


def aggregate_modelo(
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: str,
    counterpart_observation: list[str] | None = None,
    foreign_asset_observation: list[str] | None = None,
    received_invoice_retencion: list[str] | None = None,
    ledger_payment_withholding: list[str] | None = None,
) -> None:
    """Delegate per-modelo aggregation execution to the backend service."""
    _refuse_misplaced_ledger_payment_withholding(
        modelo,
        ledger_payment_withholding=ledger_payment_withholding,
        received_invoice_retencion=received_invoice_retencion,
        counterpart_observation=counterpart_observation,
        foreign_asset_observation=foreign_asset_observation,
    )
    if modelo == Modelo("123").value and received_invoice_retencion:
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.m123_ledger_payment_only"))

    command = PerModeloAggregationCommand(
        modelo=modelo,
        period=(
            _invoice_capture_period(year, period)
            if received_invoice_retencion and not ledger_payment_withholding
            else resolve_year_period(year, period, modelo=modelo)
        ),
        counterpart_observations=_parse_typed_cli_observations(
            counterpart_observation, model=CounterpartObservation, flag="--counterpart-observation"
        ),
        foreign_asset_observations=_parse_typed_cli_observations(
            foreign_asset_observation, model=ForeignAssetIngestObservation, flag="--foreign-asset-observation"
        ),
    )
    ledger_payment_requests = _parse_typed_cli_observations(
        ledger_payment_withholding,
        model=LedgerPaymentWithholdingEvidenceRequest,
        flag="--ledger-payment-withholding",
    )
    notices: list[Notice] = []
    if received_invoice_retencion:
        invoice_withholding_requests = _parse_typed_cli_observations(
            received_invoice_retencion,
            model=InvoiceWithholdingEvidenceRequest,
            flag="--received-invoice-retencion",
        )
        invoice_evidence = next(iter(invoice_withholding_requests), None)
        if modelo not in _INVOICE_EVIDENCE_MODELOS:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.aggregate.invoice_retencion_wrong_modelo",
                    modelo=modelo,
                    accepted_modelos=", ".join(sorted(_INVOICE_EVIDENCE_MODELOS)),
                )
            )
        if invoice_evidence is None:
            raise typer.BadParameter("one invoice withholding allocation is required per command")
        if len(invoice_withholding_requests) > 1:
            raise typer.BadParameter(
                "one invoice withholding allocation is accepted per command; submit each allocation explicitly"
            )
        capture = aggregate_modelo_with_received_invoice_retencion(
            ctx,
            command=command,
            evidence=invoice_evidence,
        )
        aggregate_result = _invoice_capture_aggregate_result(capture.projection)
    else:
        aggregate_projection = run_modelo_aggregate(
            ctx,
            command=command,
            ledger_payment=ledger_payment_requests[0] if ledger_payment_requests else None,
        )
        aggregate_result = _aggregate_operation_result(aggregate_projection)
        notices = _calculation_rows_absent_notices(aggregate_projection)
    lines = _aggregate_output_lines(aggregate_result, notices=notices)
    emit_envelope(ctx, command="modelo.aggregate", result=aggregate_result, lines=lines, notices=notices)


def _require_aggregate_window(projection: ModeloAggregateProjection, window: ModeloAggregateWindow | None) -> None:
    """Require a window exactly for the established periodic withholding models."""
    if projection.modelo in _PERIODIC_WINDOW_MODELOS:
        if window is None:
            raise ValueError("registered modelo aggregate omitted its withholding-window readback")
    elif window is not None:
        raise ValueError("registered modelo aggregate returned an unexpected withholding window")


def _aggregate_window_payload(
    window: ModeloAggregateWindow | None, audit: ModeloAggregateGenerationAudit | None
) -> WithholdingWindowReadbackPayload | None:
    """Project the existing baseline and optional generation audit fields."""
    return (
        None
        if window is None
        else WithholdingWindowReadbackPayload(
            baseline=WithholdingWindowBaselinePayload(
                scope_token=window.baseline.scope_token, generation_id=window.baseline.generation_id
            ),
            generation=window.generation,
            generation_audit=None
            if audit is None
            else WithholdingGenerationAuditPayload(
                parent_generation_id=audit.parent_generation_id,
                mode=audit.mode,
                supersedes_generation_id=audit.supersedes_generation_id,
            ),
        )
    )
