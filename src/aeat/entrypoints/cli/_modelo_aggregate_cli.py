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
    PerModeloAggregationCommand,
    RetencionObservation,
    WithholdingObservation,
    aggregate_per_modelo,
    persist_retencion_observations,
    persist_withholding_observations,
)
from ...core import Modelo, Period
from ...core.external_constants import RETENCIONES_MODELOS
from ...core.i18n import tr
from ._common import _emit_envelope
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
    def aggregate_modelo(
        ctx: typer.Context,
        modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.modelo.aggregate.modelo_help"))],
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
        if command.modelo == Modelo.M190.value:
            # The CLI entrypoint owns the durable write; aggregate_per_modelo stays pure.
            persist_withholding_observations(
                modelo=command.modelo,
                filing_year=command.period.filing_year,
                period=command.period,
                observations=command.withholding_observations,
            )
        if command.modelo in RETENCIONES_MODELOS:
            # Set-replace persistence keeps calculate and pull on the same observations.
            persist_retencion_observations(
                modelo=command.modelo,
                filing_year=command.period.filing_year,
                period=command.period,
                observations=command.retencion_observations,
            )
        result = aggregate_per_modelo(command)

        source_kinds = ", ".join(source_kind.value for source_kind in result.source_kinds) or "-"
        aggregate_result = ModeloAggregateResult(
            modelo=result.modelo,
            period=result.period,
            provider=result.provider.value,
            observation_count=result.log_fields.observation_count,
            source_kinds=[sk.value for sk in result.source_kinds],
            result_row_count=result.log_fields.result_row_count,
        )
        lines = [
            "operation\tmodelo.aggregate",
            f"modelo\t{result.modelo}",
            f"period\t{result.period.registry_token}",
            f"provider\t{result.provider.value}",
            f"observation_count\t{result.log_fields.observation_count}",
            f"source_kinds\t{source_kinds}",
            f"result_row_count\t{result.log_fields.result_row_count}",
        ]
        _emit_envelope(ctx, command="modelo.aggregate", result=aggregate_result, lines=lines)


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
