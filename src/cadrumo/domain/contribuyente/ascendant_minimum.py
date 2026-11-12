"""The mínimo por ascendientes (LIRPF arts. 59 and 61) of the stored ascendant rows.

Each row is one ascendant the filer declares. An ascendant generates the mínimo when,
at the devengo, it is at least the art. 59.1 age or has a disability of any age, it
lives with the filer at least half the period (art. 61 norma 5ª), its annual rentas
excluding exempt income do not exceed the art. 59.1 ceiling, and it does not file
its own return with rentas above the art. 61 norma 2ª figure. The art. 59.2
increment applies from the increment age. An ascendant who dies in the period
takes the flat art. 61 norma 4ª cuantía instead, with no increment. The amount is
shared equally among the descendants entitled to it (art. 61 norma 1ª).

Cohabitation and the sharing come from one stated fact, the number of descendants
the ascendant lives with that meet the requirements. That is the question the
Modelo 100 ascendant row asks (``CONVASDLG``), and the filer counts themself. A
stated zero says no descendant meets them, so the filer is not entitled; a count of
one or more says the filer meets them and fixes the divisor.

A fact the outcome depends on and the row does not state is never read as zero or
as eligible. The row is reported with the leaves it owes and the aggregate is
withheld. A fact a stated one already makes irrelevant is not asked for: an
ascendant whose stated rentas exceed the ceiling contributes nothing whatever else
is missing. Every euro figure and age is a registry value the caller resolves.

A comunidad deducción that rests on the mínimo reads the same entitlement: it counts
each ascendant the filer applies the mínimo for and that meets the comunidad's own age
or disability condition, by the filer's share of that ascendant.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.text_bounds import NonNegativeDecimal
from .family_fact_context import FamilyFactResolutionContext

RENTAS_ANUALES_LEAF: Final = "rentas_anuales"
DECLARACION_PROPIA_LEAF: Final = "declaracion_propia"
DISCAPACIDAD_LEAF: Final = "discapacidad"
CONVIVIENTES_LEAF: Final = "convivientes"

_MINIMUM_AGE_FACT: Final = "lirpf-art-59-ascendant-minimum-age"
_INCREMENT_AGE_FACT: Final = "lirpf-art-59-ascendant-increment-age"


class AscendantMinimumAmounts(BaseModel):
    """The registry money parameters of the mínimo por ascendientes for one edition."""

    model_config = STRICT_FROZEN_CONFIG

    base: NonNegativeDecimal
    """Art. 59.1, for each ascendant entitled."""
    increment_over_age: NonNegativeDecimal
    """Art. 59.2, added from the increment age."""
    fallecimiento: NonNegativeDecimal
    """Art. 61 norma 4ª, the flat cuantía for an ascendant who dies in the period."""
    rentas_anuales_limite: NonNegativeDecimal
    """Art. 59.1 ceiling on the ascendant's annual rentas, excluding exempt income."""
    declaracion_propia_rentas_limite: NonNegativeDecimal
    """Art. 61 norma 2ª figure above which the ascendant's own return withdraws the mínimo."""


class AscendantInfo(BaseModel):
    """One stored ascendant row, with ``None`` for each fact the row does not state."""

    model_config = STRICT_FROZEN_CONFIG

    birth_date: date
    death_date: date | None = None
    convivientes: int | None = Field(default=None, ge=0)
    """Descendants meeting the requirements the ascendant lives with, the filer included."""
    rentas_anuales_euros: Decimal | None = Field(default=None, ge=Decimal("0"))
    presenta_declaracion_propia: bool | None = None
    discapacidad_grado: int | None = Field(default=None, ge=0)
    """The statutory disability grade; ``0`` states that the ascendant has none."""

    def died_before_period(self, filing_year: int) -> bool:
        """Whether the ascendant died in an earlier period, so this one owes nothing."""
        return self.death_date is not None and self.death_date.year < filing_year

    def died_in_period(self, filing_year: int) -> bool:
        """Whether the ascendant died in the period, which the norma 4ª cuantía applies to."""
        return self.death_date is not None and self.death_date.year == filing_year

    def age_at_devengo(self, filing_year: int) -> int:
        """The age at the date art. 61 norma 3ª reads: 31 December, or the death in the period."""
        reference = date(filing_year, 12, 31)
        if self.death_date is not None and self.death_date.year == filing_year:
            reference = self.death_date
        age = reference.year - self.birth_date.year
        if (self.birth_date.month, self.birth_date.day) > (reference.month, reference.day):
            age -= 1
        return age


class AscendantFactUnstated(BaseModel):
    """A row whose share depends on facts it does not state."""

    model_config = STRICT_FROZEN_CONFIG

    position: int = Field(ge=1)
    """The row's one-based position in stored order."""
    leaves: tuple[str, ...] = Field(min_length=1)


class AscendantMinimumResult(BaseModel):
    """The aggregate, or the rows whose unstated facts withhold it."""

    model_config = STRICT_FROZEN_CONFIG

    total: Decimal | None
    unstated: tuple[AscendantFactUnstated, ...] = ()


def _entitlement(
    ascendant: AscendantInfo,
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    minimum_age: int,
) -> int | tuple[str, ...]:
    """The divisor the row's mínimo is shared by, ``0`` when a stated fact excludes it, or the leaves it owes."""
    if ascendant.died_before_period(filing_year):
        return 0
    owed: list[str] = []
    excluded = False
    if ascendant.age_at_devengo(filing_year) < minimum_age:
        if ascendant.discapacidad_grado is None:
            owed.append(DISCAPACIDAD_LEAF)
        elif ascendant.discapacidad_grado == 0:
            excluded = True
    divisor = ascendant.convivientes or 0
    if ascendant.convivientes is None:
        owed.append(CONVIVIENTES_LEAF)
    elif divisor == 0:
        excluded = True
    rentas = ascendant.rentas_anuales_euros
    if rentas is None:
        owed.append(RENTAS_ANUALES_LEAF)
    elif rentas > amounts.rentas_anuales_limite:
        excluded = True
    elif rentas > amounts.declaracion_propia_rentas_limite:
        if ascendant.presenta_declaracion_propia is None:
            owed.append(DECLARACION_PROPIA_LEAF)
        elif ascendant.presenta_declaracion_propia:
            excluded = True
    if excluded:
        return 0
    if owed:
        return tuple(owed)
    return divisor


def _share(
    ascendant: AscendantInfo,
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    minimum_age: int,
    increment_age: int,
) -> Decimal | tuple[str, ...]:
    """One row's share, or the leaves the share depends on and the row omits."""
    divisor = _entitlement(ascendant, filing_year, amounts=amounts, minimum_age=minimum_age)
    if isinstance(divisor, tuple):
        return divisor
    if divisor == 0:
        return Decimal("0")
    if ascendant.died_in_period(filing_year):
        amount = amounts.fallecimiento
    else:
        increment = ascendant.age_at_devengo(filing_year) >= increment_age
        amount = amounts.base + (amounts.increment_over_age if increment else Decimal("0"))
    return amount / Decimal(divisor)


def _comunidad_condition(
    ascendant: AscendantInfo, filing_year: int, *, qualifying_age: int, qualifying_discapacidad_grado: int
) -> bool | None:
    """Whether the row meets a comunidad's age-or-disability condition, ``None`` while its grade is unstated."""
    if ascendant.age_at_devengo(filing_year) >= qualifying_age:
        return True
    if ascendant.discapacidad_grado is None:
        return None
    return ascendant.discapacidad_grado >= qualifying_discapacidad_grado


def _weight(
    ascendant: AscendantInfo,
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    minimum_age: int,
    qualifying_age: int,
    qualifying_discapacidad_grado: int,
) -> Decimal | tuple[str, ...]:
    """One row's share of a comunidad deducción that rests on the mínimo, or the leaves it owes."""
    divisor = _entitlement(ascendant, filing_year, amounts=amounts, minimum_age=minimum_age)
    condition = _comunidad_condition(
        ascendant,
        filing_year,
        qualifying_age=qualifying_age,
        qualifying_discapacidad_grado=qualifying_discapacidad_grado,
    )
    if divisor == 0 or condition is False:
        return Decimal("0")
    if isinstance(divisor, tuple):
        return divisor if condition else tuple(dict.fromkeys((*divisor, DISCAPACIDAD_LEAF)))
    if condition is None:
        return (DISCAPACIDAD_LEAF,)
    return Decimal(1) / Decimal(divisor)


def _aggregate(shares: Sequence[Decimal | tuple[str, ...]]) -> AscendantMinimumResult:
    total = Decimal("0")
    unstated: list[AscendantFactUnstated] = []
    for position, share in enumerate(shares, start=1):
        if isinstance(share, tuple):
            unstated.append(AscendantFactUnstated(position=position, leaves=share))
        else:
            total += share
    if unstated:
        return AscendantMinimumResult(total=None, unstated=tuple(unstated))
    return AscendantMinimumResult(total=total)


def minimo_ascendientes(
    ascendants: Sequence[AscendantInfo],
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    context: FamilyFactResolutionContext,
) -> AscendantMinimumResult:
    """Sum the art. 59 mínimo of every row, or withhold it while a row owes a fact.

    Returns ``Decimal("0")`` for no rows, the legally correct figure for a filer
    with no ascendant. A row excluded by a stated fact contributes zero. Any row
    that owes a fact withholds the whole aggregate; the result names each such row
    and the leaves it owes.
    """
    minimum_age = context.integer(_MINIMUM_AGE_FACT)
    increment_age = context.integer(_INCREMENT_AGE_FACT)
    return _aggregate(
        [
            _share(ascendant, filing_year, amounts=amounts, minimum_age=minimum_age, increment_age=increment_age)
            for ascendant in ascendants
        ]
    )


def ascendant_entitlement_weighted_count(
    ascendants: Sequence[AscendantInfo],
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    context: FamilyFactResolutionContext,
    qualifying_age: int,
    qualifying_discapacidad_grado: int,
) -> AscendantMinimumResult:
    """Count the ascendants a comunidad deducción resting on the mínimo reaches, each by its share.

    An ascendant counts when the filer applies the art. 59 mínimo for them, read
    exactly as :func:`minimo_ascendientes` reads it, and the comunidad's own
    condition holds: an age at the devengo of at least ``qualifying_age``, or a
    disability grade of at least ``qualifying_discapacidad_grado``. It counts by the
    art. 61 norma 1ª share, one over the descendants entitled with the filer. A row
    a stated fact rules out, on either side, counts zero whatever else it omits; any
    other row that omits a deciding fact withholds the count, as it withholds the
    mínimo. The total is a weighted count of persons, not an amount.
    """
    minimum_age = context.integer(_MINIMUM_AGE_FACT)
    return _aggregate(
        [
            _weight(
                ascendant,
                filing_year,
                amounts=amounts,
                minimum_age=minimum_age,
                qualifying_age=qualifying_age,
                qualifying_discapacidad_grado=qualifying_discapacidad_grado,
            )
            for ascendant in ascendants
        ]
    )


__all__ = [
    "CONVIVIENTES_LEAF",
    "DECLARACION_PROPIA_LEAF",
    "DISCAPACIDAD_LEAF",
    "RENTAS_ANUALES_LEAF",
    "AscendantFactUnstated",
    "AscendantInfo",
    "AscendantMinimumAmounts",
    "AscendantMinimumResult",
    "ascendant_entitlement_weighted_count",
    "minimo_ascendientes",
]
