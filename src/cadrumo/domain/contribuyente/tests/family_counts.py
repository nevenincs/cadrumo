"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from ..family_fact_context import FamilyFactResolutionContext
from ..family_profile import RentaFamilyProfile
from ..family_types import MinimoDescendientesThresholds
from .under_three import is_eligible_menor_tres


def descendientes_menores_3_year_end(
    self: RentaFamilyProfile, filing_year: int, *, context: FamilyFactResolutionContext
) -> int:
    """Count of eligible descendientes whose age at year-end < 3 (Art. 58.2)."""
    return sum(1 for d in self.descendientes if is_eligible_menor_tres(d, filing_year, context=context))


def descendientes_eligible_minimum(
    self: RentaFamilyProfile,
    filing_year: int,
    *,
    thresholds: MinimoDescendientesThresholds,
    context: FamilyFactResolutionContext,
) -> int:
    """Count of descendientes eligible for the ordinary Art. 58.1 mínimo.

    A descendant is eligible when cohabiting, under 25 at year-end or
    carrying any discapacidad, within the Art. 58.1 rentas ceiling, and not
    excluded by Art. 61 norma 2ª — see
    :meth:`DescendantInfo.is_eligible_ordinary`.
    """
    available = self.dependencia_assimilation_available
    return sum(
        1
        for d in self.descendientes
        if d.is_eligible_ordinary(
            filing_year, thresholds=thresholds, context=context, dependencia_assimilation_available=available
        )
    )
