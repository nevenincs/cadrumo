"""Rounding-code schema axis for registry formulas."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator

__all__ = ["RegistryRoundingCode", "RegistryRoundingCodeValue"]


class RegistryRoundingCode(StrEnum):
    """Closed rounding-code vocabulary for formula results."""

    MONEY_2 = "money-2"
    INTEGER = "integer"


def _coerce_rounding_code(value: object) -> object:
    """Hydrate a raw TOML rounding string into :class:`RegistryRoundingCode`."""
    if isinstance(value, str) and not isinstance(value, RegistryRoundingCode):
        return RegistryRoundingCode(value)
    return value


RegistryRoundingCodeValue = Annotated[RegistryRoundingCode | None, BeforeValidator(_coerce_rounding_code)]
