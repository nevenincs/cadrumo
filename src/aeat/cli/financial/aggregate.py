"""`aeat financial aggregate` command for T6 casilla derivation."""

from __future__ import annotations

from decimal import Decimal

import typer

from ...config import load_settings
from ...financial._decimal import canonical_decimal
from ...financial.aggregation import (
    AggregationError,
    CasillaAggregation,
)
from ...i18n import Language, Translatable, get_translation
from .._errors import json_output_requested
from .._schemas import OutputRootSchema, emit_json_success, register_schema
from ._catalogue import catalogue_repository


@register_schema("financial aggregate")
class FinancialAggregateJson(OutputRootSchema[CasillaAggregation]):
    """Schema for ``aeat financial aggregate --json``."""


def aggregate_cmd(
    modelo: str = typer.Option(..., "--modelo", help="Modelo code, e.g. 130."),
    period: str = typer.Option(..., "--period", help="Period: YYYY-Qn, YYYYQn, YYYY-MM, or YYYY."),
    as_json: bool = typer.Option(False, "--json", help="Emit the CasillaAggregation ledger as JSON."),
) -> None:
    """Aggregate classified transactions into a casilla ledger."""

    from ...financial.aggregation._provider import FinancialFilingInputsProvider

    provider = FinancialFilingInputsProvider(repository=catalogue_repository())
    try:
        aggregation = provider.load_aggregation(modelo=modelo, period=period)
    except AggregationError:
        raise
    if as_json or json_output_requested():
        emit_json_success("financial aggregate", aggregation)
        return
    _render_human(aggregation)


def _render_human(aggregation: CasillaAggregation) -> None:
    typer.echo(
        _msg(
            {
                "es": f"Agregacion Modelo {aggregation.modelo} periodo {aggregation.period.raw}",
                "en": f"Modelo {aggregation.modelo} aggregation for {aggregation.period.raw}",
                "hu": f"{aggregation.modelo} nyomtatvany osszesites: {aggregation.period.raw}",
            }
        )
    )
    if not aggregation.casilla_values:
        typer.echo(
            _msg(
                {
                    "es": "No hay importes agregados para este periodo.",
                    "en": "No aggregated amounts for this period.",
                    "hu": "Nincs osszesitett osszeg erre az idoszakra.",
                }
            )
        )
        return
    typer.echo(
        _msg(
            {
                "es": "casilla\timporte_eur",
                "en": "casilla\tamount_eur",
                "hu": "casilla\tosszeg_eur",
            }
        )
    )
    for casilla, value in aggregation.casilla_values.items():
        typer.echo(f"{casilla}\t{_format_decimal(value)}")
    typer.echo("")
    typer.echo(
        _msg(
            {
                "es": "casilla\tcategoria_id\tsubtotal_eur\ttransaccion_ids",
                "en": "casilla\tcategory_id\tsubtotal_eur\ttransaction_ids",
                "hu": "casilla\tkategoria_id\treszosszeg_eur\ttranzakcio_ids",
            }
        )
    )
    for row in aggregation.provenance:
        typer.echo(
            "\t".join(
                [
                    row.casilla,
                    row.category_id or "",
                    _format_decimal(row.subtotal),
                    ",".join(row.transaction_ids),
                ]
            )
        )


def _output_language() -> Language:
    try:
        return Language(load_settings().aeat_output_language)
    except Exception:
        return Language.ES


def _msg(message: Translatable) -> str:
    return get_translation(message, _output_language())


def _format_decimal(value: Decimal) -> str:
    return canonical_decimal(value)


__all__ = ["FinancialAggregateJson", "aggregate_cmd"]
