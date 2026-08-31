"""Behavior handlers for modelo aggregation commands."""

from __future__ import annotations

import json
from collections.abc import Callable

import typer
from pydantic import BaseModel, ValidationError

from ...application.aggregation import (
    CounterpartObservation,
    ForeignAssetIngestObservation,
    InvoiceRetencionProjection,
    InvoiceRetencionRouteRequest,
    PerModeloAggregationCommand,
    PerModeloAggregationResult,
    RetencionObservation,
    WithholdingObservation,
    aggregate_per_modelo,
    merge_manual_and_routed_retencion_observations,
    persist_percepcion_observations,
    persist_retencion_observations,
    route_invoice_retenciones,
)
from ...application.invoices.catalogue_lifecycle import resolve_catalogue_invoice
from ...core.external_constants import RETENCIONES_MODELOS
from ...core.i18n._render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.withholding_bindings import (
    WithholdingClaveBreakdown,
    aggregate_withholding_by_clave,
)
from ._common import _load_invoices, emit_envelope
from ._modelo_behavior_support import resolve_year_period
from ._modelo_payloads import ModeloAggregateResult

ResolveYearPeriod = Callable[..., Period]


def _route_invoice_retenciones_into_command(
    command: PerModeloAggregationCommand, requests: tuple[InvoiceRetencionRouteRequest, ...]
) -> tuple[PerModeloAggregationCommand, tuple[InvoiceRetencionProjection, ...]]:
    """Merge invoice-routed retenciones into the command and return the excluded verdicts."""
    if not requests:
        return (command, ())
    if command.modelo not in RETENCIONES_MODELOS:
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.invoice_retencion_wrong_modelo", modelo=command.modelo))
    catalogue = _load_invoices()
    entries = tuple((resolve_catalogue_invoice(catalogue, request.invoice_id), request.scheme) for request in requests)
    routing = route_invoice_retenciones(entries)
    merged = command.model_copy(
        update={
            "retencion_observations": merge_manual_and_routed_retencion_observations(
                command.retencion_observations, routing.observations
            )
        }
    )
    return (merged, routing.excluded)


def _persist_cli_owned_observations(command: PerModeloAggregationCommand) -> None:
    """Write the observation sets this entrypoint owns before the pure aggregation runs."""
    if command.modelo == Modelo.M190.value:
        persist_percepcion_observations(
            modelo=command.modelo,
            filing_year=command.period.filing_year,
            period=command.period,
            observations=command.withholding_observations,
        )
    if command.modelo in RETENCIONES_MODELOS:
        persist_retencion_observations(
            modelo=command.modelo,
            filing_year=command.period.filing_year,
            period=command.period,
            observations=command.retencion_observations,
        )


def _clave_breakdown(command: PerModeloAggregationCommand) -> tuple[WithholdingClaveBreakdown, ...]:
    """Project ingested withholding detail into the modelo 190 per-clave reconciliation aid.

    A pure projection of the same store the percepciones-count resolver reads
    (one-aggregation-path), not a recomputation of the calculation engine.
    """
    if command.modelo != Modelo.M190.value:
        return ()
    return tuple(aggregate_withholding_by_clave(command.withholding_observations))


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


def _invoice_retencion_excluded_notice(projection: InvoiceRetencionProjection) -> Notice:
    """Project one excluded invoice-retención verdict into an operator-facing Notice.

    The excluded half of an :class:`~application.aggregation.InvoiceRetencionRouting`
    must be surfaced, never dropped -- an excluded retención is a liability the
    taxpayer may still owe. The guidance text is read from
    :data:`~application.aggregation.INVOICE_RETENCION_DEFECT_GUIDANCE` rather than
    invented here, so the CLI renders remediation the routing module already declared.
    """
    reasons = ", ".join(defect.value for defect in projection.defects)
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.aggregate.invoice_retencion_excluded",
        message=tr(
            "cli.app.modelo.aggregate.invoice_retencion_excluded_notice",
            invoice_id=projection.invoice_id,
            reasons=reasons,
        ),
        context={"invoice_id": projection.invoice_id, "defects": reasons},
    )


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
    command = PerModeloAggregationCommand(
        modelo=modelo,
        period=resolve_year_period(year, period, modelo=modelo),
        retencion_observations=_parse_typed_cli_observations(
            retencion_observation, model=RetencionObservation, flag="--retencion-observation"
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
    invoice_retencion_requests = _parse_typed_cli_observations(
        received_invoice_retencion, model=InvoiceRetencionRouteRequest, flag="--received-invoice-retencion"
    )
    command, excluded_invoice_retencions = _route_invoice_retenciones_into_command(command, invoice_retencion_requests)
    _persist_cli_owned_observations(command)
    result = aggregate_per_modelo(command)
    clave_breakdown = _clave_breakdown(command)
    aggregate_result = ModeloAggregateResult.from_aggregation_result(result, clave_breakdown=clave_breakdown)
    notices = [_invoice_retencion_excluded_notice(projection) for projection in excluded_invoice_retencions]
    lines = _aggregate_output_lines(result, clave_breakdown=clave_breakdown, notices=notices)
    emit_envelope(ctx, command="modelo.aggregate", result=aggregate_result, lines=lines, notices=notices)
