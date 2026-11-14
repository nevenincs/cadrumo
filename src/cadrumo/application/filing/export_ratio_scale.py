"""The casilla values as an export's design fields read them.

A design prints every rate as a percentage, while the registry may store a
ratio as a fraction of one. The box's declared scale, never the modelo, decides
which stored figures are written as their percentage, and the fixed-width
renderer and its byte check read the same values.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.ratio_scale import as_percentage, fraction_casilla_ids
from ...domain.calculations.registry.schema import ModeloRevision


def casilla_values_as_designed(
    casilla_values: Mapping[CasillaId, object], *, revision: ModeloRevision
) -> dict[CasillaId, object]:
    """Return ``casilla_values`` with each fraction-scaled ratio of ``revision`` as its percentage."""
    fractions = fraction_casilla_ids(revision.casillas)
    return {
        casilla_id: as_percentage(value) if casilla_id in fractions and isinstance(value, Decimal) else value
        for casilla_id, value in casilla_values.items()
    }


__all__ = ["casilla_values_as_designed"]
