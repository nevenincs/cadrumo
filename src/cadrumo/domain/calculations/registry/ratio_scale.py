"""How a ratio casilla's stored figure relates to the percentage its design prints.

The registry declares no unit for a ratio; only its declared maximum tells one.
A maximum of 100 stores the percentage itself, a maximum of 1 stores a fraction
of one (24 % as 0.24). A ratio declaring neither is undeclared and is never
scaled by guess.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Final

from ....core.casilla_id import CasillaId
from .schema_base import CasillaDataType
from .schema_surfaces import CasillaDefinition

_PERCENT_MAXIMUM: Final = Decimal(100)
_FRACTION_MAXIMUM: Final = Decimal(1)


class RatioScale(StrEnum):
    """The scale a ratio casilla stores its figure in."""

    PERCENT = "percent"
    FRACTION = "fraction"
    UNDECLARED = "undeclared"


def ratio_scale(data_type: str, maximum: Decimal | None) -> RatioScale | None:
    """Return the scale a ratio stores its figure in, from its declared maximum; ``None`` for any other type."""
    if data_type != CasillaDataType.RATIO:
        return None
    if maximum == _PERCENT_MAXIMUM:
        return RatioScale.PERCENT
    if maximum == _FRACTION_MAXIMUM:
        return RatioScale.FRACTION
    return RatioScale.UNDECLARED


def casilla_ratio_scale(casilla: CasillaDefinition) -> RatioScale | None:
    """Return the scale ``casilla`` stores its figure in; ``None`` when it is not a ratio."""
    maximum = casilla.constraints.max_value if casilla.constraints is not None else None
    return ratio_scale(str(casilla.data_type), maximum)


def fraction_casilla_ids(casillas: tuple[CasillaDefinition, ...]) -> frozenset[CasillaId]:
    """The ratio casillas among ``casillas`` that store their figure as a fraction of one."""
    return frozenset(casilla.id for casilla in casillas if casilla_ratio_scale(casilla) is RatioScale.FRACTION)


def as_percentage(fraction: Decimal) -> Decimal:
    """The percentage a stored fraction of one stands for."""
    return fraction * _PERCENT_MAXIMUM


__all__ = ["RatioScale", "as_percentage", "casilla_ratio_scale", "fraction_casilla_ids", "ratio_scale"]
