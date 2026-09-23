"""Behavior handlers for modelo aggregation commands."""

from __future__ import annotations

import json

import typer
from pydantic import BaseModel, ValidationError

from ...application.aggregation.counterpart import CounterpartObservation
from ...application.aggregation.foreign_assets import ForeignAssetIngestObservation
from ...application.aggregation.invoice_retencion import (
    InvoiceWithholdingEvidenceError,
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from ...application.aggregation.retenciones import RetencionObservation
from ...application.aggregation.service import (
    PerModeloAggregationCommand,
    PerModeloAggregationResult,
    aggregate_per_modelo,
)
from ...application.aggregation.withholding_observation_service import (
    WithholdingObservationMutationError,
    WithholdingWindowScope,
)
from ...application.aggregation.withholding_producer import WithholdingProducerError
from ...application.aggregation.withholding_recognition import WithholdingRecognitionError
from ...core.i18n.render import tr
from ...core.json_contract import Notice
from ...core.modelo import Modelo
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.withholding_bindings import (
    WithholdingClaveBreakdown,
    WithholdingObservation,
    aggregate_withholding_by_clave,
)
from ._modelo_behavior_support import resolve_year_period
from ._modelo_payloads import ModeloAggregateResult, WithholdingWindowReadbackPayload
from .common import active_bucket_id_or_refuse, emit_envelope
from .state_projection_support import (
    authority_operation,
    retencion_observation_ports_factory,
    withholding_observation_service,
)

_INVOICE_WITHHOLDING_MODELOS = frozenset({"111", "115", "123"})


def _capture_invoice_withholding_into_command(
    ctx: typer.Context,
    command: PerModeloAggregationCommand,
    requests: tuple[InvoiceWithholdingEvidenceRequest, ...],
    *,
    has_caller_authored_retenciones: bool,
) -> PerModeloAggregationCommand:
    """Capture one canonical-invoice allocation, then read its active projection.

    The existing aggregate command remains a reporting projection: 111, 115,
    and 123 must never use it as a writable retención transport. Reading the
    active encrypted projection after the shared service succeeds also makes
    omission a genuine no-op rather than an empty set replacement.
    """
    if command.modelo not in _INVOICE_WITHHOLDING_MODELOS:
        if requests:
            raise typer.BadParameter(
                tr("cli.app.modelo.aggregate.invoice_retencion_wrong_modelo", modelo=command.modelo)
            )
        return command
    if has_caller_authored_retenciones:
        raise typer.BadParameter(
            f"--retencion-observation is not accepted for Modelo {command.modelo}; use invoice evidence"
        )
    if len(requests) > 1:
        raise typer.BadParameter(
            "one invoice withholding allocation is accepted per command; submit each allocation explicitly"
        )

    bucket_id = active_bucket_id_or_refuse()
    ports = retencion_observation_ports_factory(ctx)(bucket_id=bucket_id)
    if not requests:
        return command.model_copy(
            update={"retencion_observations": ports.repository.load_observations(command.modelo, command.period)}
        )

    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ...application.invoices.catalogue_lifecycle import resolve_catalogue_invoice

    catalogue, catalogue_revision_id = InvoiceCatalogueRepository(bucket_id=bucket_id).load_revisioned()
    try:
        invoice = resolve_catalogue_invoice(catalogue, requests[0].invoice_id)
        capture = build_invoice_withholding_capture(
            invoice,
            catalogue_revision_id=catalogue_revision_id,
            request=requests[0],
            applicable_year=command.period.filing_year,
        )
    except (InvoiceWithholdingEvidenceError, WithholdingRecognitionError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if capture.scope.modelo != command.modelo or capture.scope.period != command.period:
        raise typer.BadParameter("derived recognition period does not match the requested modelo period")

    try:
        from ...application.aggregation.withholding_producer import WithholdingProducer

        WithholdingProducer(service=withholding_observation_service(ctx, bucket_id=bucket_id)).capture(capture.command)
    except (
        WithholdingProducerError,
        WithholdingRecognitionError,
        WithholdingObservationMutationError,
        ValueError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc
    return command.model_copy(
        update={"retencion_observations": ports.repository.load_observations(command.modelo, command.period)}
    )


def _clave_breakdown(command: PerModeloAggregationCommand) -> tuple[WithholdingClaveBreakdown, ...]:
    """Project ingested withholding detail into the modelo 190 per-clave reconciliation aid.

    A pure projection of the same store the percepciones-count resolver reads
    (one-aggregation-path), not a recomputation of the calculation engine.
    """
    if command.modelo != Modelo("190").value:
        return ()
    return tuple(aggregate_withholding_by_clave(command.withholding_observations))


def _withholding_window_readback(
    ctx: typer.Context,
    command: PerModeloAggregationCommand,
) -> WithholdingWindowReadbackPayload | None:
    """Read the current exact mutation baseline without exposing evidence rows.

    Invoice-backed withholding capture and an omitted aggregate invocation
    both arrive here after the shared producer has either committed or made no
    change.  The read is intentionally separate from the aggregation result:
    it preserves the service's optimistic-concurrency and immutable-generation
    contracts instead of reconstructing a token from aggregation data.
    """
    if command.modelo not in _INVOICE_WITHHOLDING_MODELOS:
        return None
    scope = WithholdingWindowScope(modelo=command.modelo, period=command.period)
    service = withholding_observation_service(ctx, bucket_id=active_bucket_id_or_refuse())
    state = service.read_window(scope)
    generation_audit = None if state.generation == 0 else service.read_generation(scope, state.baseline.generation_id)
    return WithholdingWindowReadbackPayload.from_window_state(state, generation_audit=generation_audit)


def _aggregate_output_lines(
    result: PerModeloAggregationResult, *, clave_breakdown: tuple[WithholdingClaveBreakdown, ...], notices: list[Notice]
) -> list[str]:
    """Render the text envelope lines for one per-modelo aggregation."""
    source_kinds = ", ".join(source_kind.value for source_kind in result.source_kinds) or "-"
    lines = [
        "operation\tmodelo.aggregate",
        f"modelo\t{result.modelo}",
        f"period\t{result.period.registry_token}",
        f"provider\t{result.provider.value}",
        f"observation_count\t{result.log_fields.observation_count}",
        f"source_kinds\t{source_kinds}",
        f"result_row_count\t{result.log_fields.result_row_count}",
    ]
    if clave_breakdown:
        lines.append("clave\tpercepcion_count\tpercibido_total\tretencion_total")
        lines.extend(
            f"clave_breakdown\t{row.clave.value}\t{row.percepcion_count}\t{row.percibido_total}\t{row.retencion_total}"
            for row in clave_breakdown
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
    retencion_observation: list[str] | None = None,
    counterpart_observation: list[str] | None = None,
    foreign_asset_observation: list[str] | None = None,
    withholding_observation: list[str] | None = None,
    received_invoice_retencion: list[str] | None = None,
) -> None:
    """Delegate per-modelo aggregation execution to the backend service."""
    operation = authority_operation(ctx)
    with validating_governed_facts(operation):
        if modelo == Modelo("123").value and (retencion_observation or received_invoice_retencion):
            raise typer.BadParameter(
                "Modelo 123 public capture is incomplete: the current Número de rentas count and "
                "Modelo 193 annual disclosure cannot yet be verified; no withholding evidence was written"
            )
        if modelo == Modelo("190").value and withholding_observation:
            raise typer.BadParameter(
                "--withholding-observation is not accepted for Modelo 190; "
                "capture annual detail with invoice evidence on Modelo 111"
            )
        command = PerModeloAggregationCommand(
            modelo=modelo,
            period=resolve_year_period(year, period, modelo=modelo),
            retencion_observations=(
                ()
                if modelo in _INVOICE_WITHHOLDING_MODELOS
                else _parse_typed_cli_observations(
                    retencion_observation, model=RetencionObservation, flag="--retencion-observation"
                )
            ),
            counterpart_observations=_parse_typed_cli_observations(
                counterpart_observation, model=CounterpartObservation, flag="--counterpart-observation"
            ),
            foreign_asset_observations=_parse_typed_cli_observations(
                foreign_asset_observation, model=ForeignAssetIngestObservation, flag="--foreign-asset-observation"
            ),
            withholding_observations=_parse_typed_cli_observations(
                withholding_observation, model=WithholdingObservation, flag="--withholding-observation"
            ),
        )
        invoice_withholding_requests = _parse_typed_cli_observations(
            received_invoice_retencion,
            model=InvoiceWithholdingEvidenceRequest,
            flag="--received-invoice-retencion",
        )
        command = _capture_invoice_withholding_into_command(
            ctx,
            command,
            invoice_withholding_requests,
            has_caller_authored_retenciones=bool(retencion_observation),
        )
    result = aggregate_per_modelo(command, operation=operation)
    clave_breakdown = _clave_breakdown(command)
    aggregate_result = ModeloAggregateResult.from_aggregation_result(
        result,
        clave_breakdown=clave_breakdown,
        withholding_window=_withholding_window_readback(ctx, command),
    )
    notices: list[Notice] = []
    lines = _aggregate_output_lines(result, clave_breakdown=clave_breakdown, notices=notices)
    emit_envelope(ctx, command="modelo.aggregate", result=aggregate_result, lines=lines, notices=notices)
