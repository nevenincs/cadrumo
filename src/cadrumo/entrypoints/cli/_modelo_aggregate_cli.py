"""Typer registration for modelo aggregation commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated

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
from ...application.invoices import resolve_catalogue_invoice
from ...core import Modelo, Period
from ...core.external_constants import RETENCIONES_MODELOS
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.calculations.registry import WithholdingClaveBreakdown, aggregate_withholding_by_clave
from ._command_policy import command_execution_policy
from ._common import MODELO_CODE_CHOICE, _emit_envelope, _load_invoices
from ._modelo_execution_policies import CALCULATION_WRITE
from ._modelo_payloads import ModeloAggregateResult

ResolveYearPeriod = Callable[..., Period]


def register_aggregate_commands(app: typer.Typer, *, resolve_year_period: ResolveYearPeriod) -> None:
    """Register per-modelo aggregation commands."""

    @app.command(
        "aggregate",
        help=tr(
            "cli.app.modelo.aggregate_help",
            default=(
                "Run the backend per-modelo aggregation service from explicit canonical observations "
                "(ledger_transaction, purchase_invoice_evidence, payable_invoice, collectible_invoice)."
            ),
        ),
    )
    @command_execution_policy(CALCULATION_WRITE)
    def aggregate_modelo(
        ctx: typer.Context,
        modelo: Annotated[
            str,
            typer.Option("--modelo", click_type=MODELO_CODE_CHOICE, help=tr("cli.app.modelo.aggregate.modelo_help")),
        ],
        year: Annotated[int, typer.Option("--year", help=tr("cli.app.modelo.work.year_help"))],
        period: Annotated[str, typer.Option("--period", help=tr("cli.app.modelo.aggregate.period_help"))],
        retencion_observation: Annotated[
            list[str] | None,
            typer.Option(
                "--retencion-observation",
                help=tr("cli.app.modelo.aggregate.retencion_observation_help"),
            ),
        ] = None,
        counterpart_observation: Annotated[
            list[str] | None,
            typer.Option(
                "--counterpart-observation",
                help=tr("cli.app.modelo.aggregate.counterpart_observation_help"),
            ),
        ] = None,
        foreign_asset_observation: Annotated[
            list[str] | None,
            typer.Option(
                "--foreign-asset-observation",
                help=tr("cli.app.modelo.aggregate.foreign_asset_observation_help"),
            ),
        ] = None,
        withholding_observation: Annotated[
            list[str] | None,
            typer.Option(
                "--withholding-observation",
                help=tr("cli.app.modelo.aggregate.withholding_observation_help"),
            ),
        ] = None,
        received_invoice_retencion: Annotated[
            list[str] | None,
            typer.Option(
                "--received-invoice-retencion",
                help=tr("cli.app.modelo.aggregate.received_invoice_retencion_help"),
            ),
        ] = None,
    ) -> None:
        """Delegate per-modelo aggregation execution to the backend service."""
        command = PerModeloAggregationCommand(
            modelo=modelo,
            period=resolve_year_period(year, period, modelo=modelo),
            retencion_observations=_parse_typed_cli_observations(
                retencion_observation,
                model=RetencionObservation,
                flag="--retencion-observation",
            ),
            counterpart_observations=_parse_typed_cli_observations(
                counterpart_observation,
                model=CounterpartObservation,
                flag="--counterpart-observation",
            ),
            foreign_asset_observations=_parse_typed_cli_observations(
                foreign_asset_observation,
                model=ForeignAssetIngestObservation,
                flag="--foreign-asset-observation",
            ),
            withholding_observations=_parse_typed_cli_observations(
                withholding_observation,
                model=WithholdingObservation,
                flag="--withholding-observation",
            ),
        )
        invoice_retencion_requests = _parse_typed_cli_observations(
            received_invoice_retencion,
            model=InvoiceRetencionRouteRequest,
            flag="--received-invoice-retencion",
        )
        command, excluded_invoice_retencions = _route_invoice_retenciones_into_command(
            command,
            invoice_retencion_requests,
        )
        _persist_cli_owned_observations(command)
        result = aggregate_per_modelo(command)

        clave_breakdown = _clave_breakdown(command)
        aggregate_result = ModeloAggregateResult.from_aggregation_result(
            result,
            clave_breakdown=clave_breakdown,
        )
        notices = [_invoice_retencion_excluded_notice(projection) for projection in excluded_invoice_retencions]
        lines = _aggregate_output_lines(result, clave_breakdown=clave_breakdown, notices=notices)
        _emit_envelope(ctx, command="modelo.aggregate", result=aggregate_result, lines=lines, notices=notices)


def _route_invoice_retenciones_into_command(
    command: PerModeloAggregationCommand,
    requests: tuple[InvoiceRetencionRouteRequest, ...],
) -> tuple[PerModeloAggregationCommand, tuple[InvoiceRetencionProjection, ...]]:
    """Merge invoice-routed retenciones into the command and return the excluded verdicts."""
    if not requests:
        return command, ()
    if command.modelo not in RETENCIONES_MODELOS:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.aggregate.invoice_retencion_wrong_modelo",
                modelo=command.modelo,
            ),
        )
    catalogue = _load_invoices()
    entries = tuple((resolve_catalogue_invoice(catalogue, request.invoice_id), request.scheme) for request in requests)
    routing = route_invoice_retenciones(entries)
    # merge_manual_and_routed_retencion_observations refuses a collision, so an
    # invoice both hand-typed via --retencion-observation and auto-routed here
    # is a loud error rather than a silent pick or a double-counted rollup.
    merged = command.model_copy(
        update={
            "retencion_observations": merge_manual_and_routed_retencion_observations(
                command.retencion_observations,
                routing.observations,
            ),
        },
    )
    return merged, routing.excluded


def _persist_cli_owned_observations(command: PerModeloAggregationCommand) -> None:
    """Write the observation sets this entrypoint owns before the pure aggregation runs."""
    if command.modelo == Modelo.M190.value:
        # The CLI entrypoint owns the durable write; aggregate_per_modelo stays pure.
        persist_percepcion_observations(
            modelo=command.modelo,
            filing_year=command.period.filing_year,
            period=command.period,
            observations=command.withholding_observations,
        )
    if command.modelo in RETENCIONES_MODELOS:
        # Set-replace persistence keeps calculate and pull on the same observations,
        # now including any invoice-routed rows merged above.
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
    result: PerModeloAggregationResult,
    *,
    clave_breakdown: tuple[WithholdingClaveBreakdown, ...],
    notices: list[Notice],
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
    values: list[str] | None,
    *,
    model: type[ObservationT],
    flag: str,
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
            # model_validate_json uses pydantic JSON coercions at the transport boundary.
            parsed.append(model.model_validate_json(raw))
        except ValidationError as exc:
            details = "; ".join(f"{'.'.join(str(s) for s in e['loc'])}: {e['msg']}" for e in exc.errors())
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.aggregate.json_validation_error",
                    flag=flag,
                    details=details,
                ),
            ) from exc
    return tuple(parsed)


__all__ = ["register_aggregate_commands"]
