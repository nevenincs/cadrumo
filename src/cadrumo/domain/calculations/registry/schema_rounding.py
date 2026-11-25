"""Rounding-code schema axis for registry formulas."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator

__all__ = ["RegistryRoundingCode", "RegistryRoundingCodeValue"]


class RegistryRoundingCode(StrEnum):
    """Closed rounding-code vocabulary for formula results.

    Each member names one rounding MODE; the mode is never inferred from
    the target's data type, because two formulas producing the same data
    type can be bound by different legal rounding rules.

    * ``MONEY_2`` — two decimals, half-up, per the AEAT Instrucciones
      (:func:`core.money.rounding.round_to_cents`).
    * ``INTEGER`` — whole units, half-up. The neutral integer mode for a
      target the law does not direct a specific way (e.g. a count of
      perceptores).
    * ``INTEGER_CEILING`` — whole units, always toward the next unit up
      (``ROUND_CEILING``), never half-up. Required wherever the governing
      provision says the result is taken to the *unidad superior*: LIVA
      art. 104.Dos closes its prorrata-general apartado with "La prorrata
      de deducción resultante de la aplicación de los criterios anteriores
      se redondeará en la unidad superior", so a 55,2 % ratio is a 56 %
      deduction right, not 55 %. Half-up would understate the deduction
      for every ratio whose fractional part is at or below one half.
    * ``DECIMAL_2_TRUNCATED`` — two decimals, truncated (``ROUND_DOWN``,
      toward zero), never half-up. Required wherever the governing
      provision says the figure is "expresado con dos decimales sin
      redondeo": LIRPF art. 63.2 and 74.2 for the tipo medio de gravamen
      general estatal / autonómico, as the Manual práctico de Renta Parte 1
      restates it ("se expresará con dos decimales sin redondeo"). A cuota
      of 2.475 over a base of 26.800 is 9,23 %, not the half-up 9,24 %.
      Truncation toward zero equals truncation downward only for a
      non-negative result; every target enrolled here is a tipo medio
      guarded by a positive base, so it is never negative.
    """

    MONEY_2 = "money-2"
    INTEGER = "integer"
    INTEGER_CEILING = "integer-ceiling"
    DECIMAL_2_TRUNCATED = "decimal-2-truncated"


def _coerce_rounding_code(value: object) -> object:
    """Hydrate a raw TOML rounding string into :class:`RegistryRoundingCode`."""
    if isinstance(value, str) and not isinstance(value, RegistryRoundingCode):
        return RegistryRoundingCode(value)
    return value


RegistryRoundingCodeValue = Annotated[RegistryRoundingCode | None, BeforeValidator(_coerce_rounding_code)]
