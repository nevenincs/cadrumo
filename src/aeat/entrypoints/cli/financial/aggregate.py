"""Implement the ``aeat financial aggregate`` Typer command.

Bridges the financial-input pipeline to the casilla derivation stage by
loading classified transactions through
:class:`aeat.application.aggregation._provider.FinancialFilingInputsProvider`
and rendering the resulting :class:`aeat.application.aggregation.CasillaAggregation`
ledger as either human-readable tables or canonical JSON.
"""

from __future__ import annotations

from decimal import Decimal

import typer
from pydantic import ValidationError

from ....adapters.inbound.financial._decimal import canonical_decimal
from ....application.aggregation import (
    AggregationError,
    CasillaAggregation,
)
from ....core.config import load_settings
from ....core.i18n import Language, Translatable, get_translation
from ....core.logging import get_logger
from .._errors import json_output_requested
from .._schemas import OutputRootSchema, emit_json_success, register_schema
from ._catalogue import catalogue_repository

_logger = get_logger(__name__)


@register_schema("financial aggregate")
class FinancialAggregateJson(OutputRootSchema[CasillaAggregation]):
    """JSON envelope schema for ``aeat financial aggregate --json``.

    Specialises :class:`aeat.entrypoints.cli._schemas.OutputRootSchema`
    over :class:`aeat.application.aggregation.CasillaAggregation` so the
    contract test suite can validate emitted output against a single
    pydantic model.
    """


def aggregate_cmd(
    modelo: str = typer.Option(..., "--modelo", help="Modelo code, e.g. 130."),
    period: str = typer.Option(..., "--period", help="Period: YYYY-Qn, YYYYQn, YYYY-MM, or YYYY."),
    as_json: bool = typer.Option(False, "--json", help="Emit the CasillaAggregation ledger as JSON."),
) -> None:
    """Aggregate classified transactions into a casilla ledger.

    Loads the persisted transaction catalogue, derives the casilla totals
    via :class:`aeat.application.aggregation._provider.FinancialFilingInputsProvider`,
    and emits the result either as a human-readable summary or as the
    JSON envelope defined by :class:`FinancialAggregateJson`.

    Args:
        modelo: AEAT modelo code (e.g. ``"130"``) the aggregation targets.
        period: Period selector accepted by the provider — ``YYYY-Qn``,
            ``YYYYQn``, ``YYYY-MM``, or ``YYYY``.
        as_json: When ``True`` (or when the global ``--json`` flag was
            supplied) emit the ledger via :func:`emit_json_success`
            instead of the human-readable rendering.

    Raises:
        :exc:`aeat.application.aggregation.AggregationError`: When the
            provider rejects the requested modelo / period combination.
    """

    from ....application.aggregation._provider import FinancialFilingInputsProvider

    provider = FinancialFilingInputsProvider(repository=catalogue_repository())
    try:
        aggregation = provider.load_aggregation(modelo=modelo, period=period)
    except AggregationError:
        _logger.warning(
            "aggregate: aggregation failed for modelo=%s period=%s",
            modelo,
            period,
            exc_info=True,
        )
        raise
    if as_json or json_output_requested():
        emit_json_success("financial aggregate", aggregation)
        return
    _render_human(aggregation)


def _render_human(aggregation: CasillaAggregation) -> None:
    """Print the casilla ledger and provenance rows in the operator language."""
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
    """Resolve the configured operator output language, falling back to Spanish."""
    try:
        return Language(load_settings().aeat_output_language)
    except (ValueError, ValidationError):
        _logger.warning("aggregate: failed to resolve output language; falling back to es", exc_info=True)
        return Language.ES


def _msg(message: Translatable) -> str:
    """Return ``message`` translated into the configured operator language."""
    return get_translation(message, _output_language())


def _format_decimal(value: Decimal) -> str:
    """Render a :class:`decimal.Decimal` using the canonical financial format."""
    return canonical_decimal(value)


__all__ = ["aggregate_cmd"]
