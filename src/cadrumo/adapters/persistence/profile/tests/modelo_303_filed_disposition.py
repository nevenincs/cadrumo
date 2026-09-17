"""Seed a filed Modelo 303 whose declared disposition agrees with its result.

Official Modelo 303 observations must carry the declaration-type header and a
result whose sign supports that declaration. A seed that only states the
carried compensation balance is completed here as the filing that generated
it: a negative result whose compensation was requested.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.observed_header_fact import ObservedHeaderFact

_RESULT_CASILLA: CasillaId = validated_casilla_id("iva.resultado", surface="modelo 303 filed seed")
_AVAILABLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-disponible-fin-periodo",
    surface="modelo 303 filed seed",
)


def _declaration_type(result: Decimal) -> str:
    if result < 0:
        return "C"
    if result == 0:
        return "N"
    return "I"


def modelo_303_filed_disposition(
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    source_locator: str,
) -> tuple[dict[CasillaId, Decimal], tuple[ObservedHeaderFact, ...]]:
    """Return the completed casilla values and the declaration-type header."""
    completed = dict(casilla_values)
    completed.setdefault(_RESULT_CASILLA, -completed.get(_AVAILABLE_CASILLA, Decimal("0")))
    header = ObservedHeaderFact(
        header_key="declaration_type",
        value=_declaration_type(completed[_RESULT_CASILLA]),
        source_artefact_kind="submitted_file",
        source_locator=source_locator,
    )
    return completed, (header,)


__all__ = ["modelo_303_filed_disposition"]
