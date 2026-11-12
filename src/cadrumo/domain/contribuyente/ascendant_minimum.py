"""The mínimo por ascendientes (LIRPF arts. 59 and 61) of the stored ascendant rows.

Each row is one ascendant the filer declares. An ascendant generates the mínimo when,
at the devengo, it is at least the art. 59.1 age or has a disability of any age, it
lives with the filer at least half the period (art. 61 norma 5ª), its annual rentas
excluding exempt income do not exceed the art. 59.1 ceiling, and it does not file
its own return with rentas above the art. 61 norma 2ª figure. The art. 59.2
increment applies from the increment age. An ascendant who dies in the period
takes the flat art. 61 norma 4ª cuantía instead, with no increment. The amount is
shared equally among the descendants entitled to it (art. 61 norma 1ª).

The sharing comes from one stated fact, the number of descendants the ascendant
lives with that meet the requirements. That is the question the Modelo 100 ascendant
row asks (``CONVASDLG``), and the filer counts themself. A stated zero says no
descendant meets them, so the filer is not entitled; a count of one or more says the
filer meets them and fixes the divisor. Whether the ascendant lived with the filer at
least half the period (art. 61 norma 5ª, up to the death date for an ascendant who
died in it; an internment in a specialised centre counts, art. 59.1) is a fact of its
own: a stated no excludes the row.

Every circumstance is the one at the devengo, or at the death date for an ascendant
who died in the period (art. 61 normas 3ª and 4ª). A disability is a grade of at
least the art. 60.3 threshold. A judicial declaration of incapacity counts as the
art. 60.3 higher grade whatever grade is stated, so it governs over a lower one.

A fact the outcome depends on and the row does not state is never read as zero or
as eligible. The row is reported with the leaves it owes and the aggregate is
withheld. A fact a stated one already makes irrelevant is not asked for: an
ascendant whose stated rentas exceed the ceiling contributes nothing whatever else
is missing. Every euro figure, age and grade is a registry value the caller resolves.

A comunidad deducción that rests on the mínimo reads the same entitlement: it counts
each ascendant the filer applies the mínimo for and that meets the comunidad's own age
or disability condition, by the filer's share of that ascendant.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.text_bounds import NonNegativeDecimal
from .family_fact_context import FamilyFactResolutionContext

RENTAS_ANUALES_LEAF: Final = "rentas_anuales"
DECLARACION_PROPIA_LEAF: Final = "declaracion_propia"
DISCAPACIDAD_LEAF: Final = "discapacidad"
DISCAPACIDAD_ASISTENCIA_LEAF: Final = "discapacidad_asistencia"
INCAPACIDAD_JUDICIAL_LEAF: Final = "incapacidad_judicial"
CONVIVIENTES_LEAF: Final = "convivientes"
CONVIVENCIA_MITAD_PERIODO_LEAF: Final = "convivencia_mitad_periodo"

_MINIMUM_AGE_FACT: Final = "lirpf-art-59-ascendant-minimum-age"
_INCREMENT_AGE_FACT: Final = "lirpf-art-59-ascendant-increment-age"
_DISABILITY_GRADE_FACT: Final = "lirpf-art-60-disability-minimum-grade"
_JUDICIAL_INCAPACITY_GRADE_FACT: Final = "lirpf-art-60-judicial-incapacity-grade"


class AscendantDisabilityKey(StrEnum):
    """The disability circumstance the Modelo 100 ascendant row reports (``PCTMINASDLG``).

    Each member names one value of the official key; the design's code for it is
    registry data. A row with no disability reports none.
    """

    GRADE_FROM_MINIMUM = "grade_from_minimum"
    """A grade from the art. 60.3 threshold up to below the higher grade."""
    GRADE_FROM_MINIMUM_WITH_ASSISTANCE = "grade_from_minimum_with_assistance"
    """The same grade, with assistance of third persons or reduced mobility."""
    GRADE_FROM_HIGHER = "grade_from_higher"
    """A grade of at least the higher grade, without a judicial incapacity."""
    INCAPACIDAD_JUDICIAL = "incapacidad_judicial"
    """An incapacity declared by a judicial resolution of the civil jurisdiction."""


@dataclass(frozen=True, slots=True)
class DisabilityGrades:
    """The art. 60.3 grades for one edition: the disability threshold and the higher grade."""

    minimum: int
    higher: int
    """The grade a judicial incapacity counts as."""

    @classmethod
    def resolve(cls, context: FamilyFactResolutionContext) -> DisabilityGrades:
        """Read both grades from the registry for the context's period."""
        return cls(
            minimum=context.integer(_DISABILITY_GRADE_FACT),
            higher=context.integer(_JUDICIAL_INCAPACITY_GRADE_FACT),
        )


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
    convivencia_mitad_periodo: bool | None = None
    """Whether the ascendant lived with the filer at least half the period (art. 61 norma 5ª)."""
    rentas_anuales_euros: Decimal | None = Field(default=None, ge=Decimal("0"))
    presenta_declaracion_propia: bool | None = None
    discapacidad_grado: int | None = Field(default=None, ge=0)
    """The statutory disability grade; ``0`` states that the ascendant has none."""
    discapacidad_asistencia: bool | None = None
    """Whether the ascendant needs assistance of third persons or has reduced mobility (art. 60.2)."""
    incapacidad_judicial: bool | None = None
    """Whether a judicial resolution of the civil jurisdiction declares the ascendant's incapacity."""

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

    def effective_grade(self, grades: DisabilityGrades) -> int | None:
        """The grade art. 60.3 reads: at least the higher grade under a judicial incapacity, else the stated one.

        ``None`` while the grade is unstated and no judicial incapacity is stated.
        """
        if self.incapacidad_judicial is True:
            return max(self.discapacidad_grado or 0, grades.higher)
        return self.discapacidad_grado

    def has_disability(self, grades: DisabilityGrades) -> bool | None:
        """Whether the ascendant has a disability, ``None`` while a fact that could give one is unstated.

        A stated grade below the threshold leaves only a judicial incapacity to decide it.
        """
        grade = self.effective_grade(grades)
        if grade is not None and grade >= grades.minimum:
            return True
        if grade is None or self.incapacidad_judicial is None:
            return None
        return False

    def disability_key(self, grades: DisabilityGrades) -> AscendantDisabilityKey | None:
        """The ``PCTMINASDLG`` circumstance, ``None`` with no disability or while a fact deciding it is unstated."""
        if self.incapacidad_judicial is True:
            return AscendantDisabilityKey.INCAPACIDAD_JUDICIAL
        grade = self.discapacidad_grado
        if grade is None or grade < grades.minimum or self.incapacidad_judicial is None:
            return None
        if grade >= grades.higher:
            return AscendantDisabilityKey.GRADE_FROM_HIGHER
        if self.discapacidad_asistencia is None:
            return None
        if self.discapacidad_asistencia:
            return AscendantDisabilityKey.GRADE_FROM_MINIMUM_WITH_ASSISTANCE
        return AscendantDisabilityKey.GRADE_FROM_MINIMUM


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


@dataclass(frozen=True, slots=True)
class _Thresholds:
    minimum_age: int
    grades: DisabilityGrades


def _thresholds(context: FamilyFactResolutionContext) -> _Thresholds:
    return _Thresholds(minimum_age=context.integer(_MINIMUM_AGE_FACT), grades=DisabilityGrades.resolve(context))


def _undecided_grade_leaves(ascendant: AscendantInfo) -> tuple[str, ...]:
    """The unstated leaves that leave a row's grade undecided."""
    leaves = (
        (DISCAPACIDAD_LEAF, ascendant.discapacidad_grado),
        (INCAPACIDAD_JUDICIAL_LEAF, ascendant.incapacidad_judicial),
    )
    return tuple(leaf for leaf, value in leaves if value is None)


def _age_excludes(ascendant: AscendantInfo, filing_year: int, *, thresholds: _Thresholds, owed: list[str]) -> bool:
    """Whether a row under the minimum age has no disability; ``owed`` gains the facts that could give one."""
    if ascendant.age_at_devengo(filing_year) >= thresholds.minimum_age:
        return False
    disability = ascendant.has_disability(thresholds.grades)
    if disability is None:
        owed.extend(_undecided_grade_leaves(ascendant))
        return False
    return not disability


def _cohabitation_excludes(ascendant: AscendantInfo, *, owed: list[str]) -> bool:
    """Whether the row's stated cohabitation excludes it; ``owed`` gains the cohabitation facts it omits."""
    excluded = False
    if ascendant.convivientes is None:
        owed.append(CONVIVIENTES_LEAF)
    elif ascendant.convivientes == 0:
        excluded = True
    if ascendant.convivencia_mitad_periodo is None:
        owed.append(CONVIVENCIA_MITAD_PERIODO_LEAF)
    elif not ascendant.convivencia_mitad_periodo:
        excluded = True
    return excluded


def _rentas_exclude(ascendant: AscendantInfo, amounts: AscendantMinimumAmounts, *, owed: list[str]) -> bool:
    """Whether the row's stated rentas or own return exclude it; ``owed`` gains the facts it omits."""
    rentas = ascendant.rentas_anuales_euros
    if rentas is None:
        owed.append(RENTAS_ANUALES_LEAF)
        return False
    if rentas > amounts.rentas_anuales_limite:
        return True
    if rentas <= amounts.declaracion_propia_rentas_limite:
        return False
    if ascendant.presenta_declaracion_propia is None:
        owed.append(DECLARACION_PROPIA_LEAF)
        return False
    return bool(ascendant.presenta_declaracion_propia)


def _entitlement(
    ascendant: AscendantInfo,
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    thresholds: _Thresholds,
) -> int | tuple[str, ...]:
    """The divisor the row's mínimo is shared by, ``0`` when a stated fact excludes it, or the leaves it owes."""
    if ascendant.died_before_period(filing_year):
        return 0
    owed: list[str] = []
    excluded = _age_excludes(ascendant, filing_year, thresholds=thresholds, owed=owed)
    if _cohabitation_excludes(ascendant, owed=owed):
        excluded = True
    if _rentas_exclude(ascendant, amounts, owed=owed):
        excluded = True
    if excluded:
        return 0
    if owed:
        return tuple(owed)
    return ascendant.convivientes or 0


def _share(
    ascendant: AscendantInfo,
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    thresholds: _Thresholds,
    increment_age: int,
) -> Decimal | tuple[str, ...]:
    """One row's share, or the leaves the share depends on and the row omits."""
    divisor = _entitlement(ascendant, filing_year, amounts=amounts, thresholds=thresholds)
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
    ascendant: AscendantInfo,
    filing_year: int,
    *,
    grades: DisabilityGrades,
    qualifying_age: int,
    qualifying_discapacidad_grado: int,
) -> bool | None:
    """Whether the row meets a comunidad's age-or-disability condition, ``None`` while its grade is undecided.

    The grade is the art. 60.3 one, so a judicial incapacity counts as the higher grade.
    """
    if ascendant.age_at_devengo(filing_year) >= qualifying_age:
        return True
    grade = ascendant.effective_grade(grades)
    if grade is not None and grade >= qualifying_discapacidad_grado:
        return True
    if grade is None or ascendant.incapacidad_judicial is None:
        return None
    return False


def _weight(
    ascendant: AscendantInfo,
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    thresholds: _Thresholds,
    qualifying_age: int,
    qualifying_discapacidad_grado: int,
) -> Decimal | tuple[str, ...]:
    """One row's share of a comunidad deducción that rests on the mínimo, or the leaves it owes."""
    divisor = _entitlement(ascendant, filing_year, amounts=amounts, thresholds=thresholds)
    condition = _comunidad_condition(
        ascendant,
        filing_year,
        grades=thresholds.grades,
        qualifying_age=qualifying_age,
        qualifying_discapacidad_grado=qualifying_discapacidad_grado,
    )
    if divisor == 0 or condition is False:
        return Decimal("0")
    if condition is None:
        undecided = _undecided_grade_leaves(ascendant)
        return tuple(dict.fromkeys((*divisor, *undecided))) if isinstance(divisor, tuple) else undecided
    if isinstance(divisor, tuple):
        return divisor
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
    thresholds = _thresholds(context)
    increment_age = context.integer(_INCREMENT_AGE_FACT)
    return _aggregate(
        [
            _share(ascendant, filing_year, amounts=amounts, thresholds=thresholds, increment_age=increment_age)
            for ascendant in ascendants
        ]
    )


def disability_minimum_positions(
    ascendants: Sequence[AscendantInfo],
    filing_year: int,
    *,
    amounts: AscendantMinimumAmounts,
    context: FamilyFactResolutionContext,
) -> tuple[int, ...]:
    """The one-based positions of the rows the art. 60.2 disability minimum reaches.

    A row counts when the filer applies the art. 59 mínimo for it, read as
    :func:`minimo_ascendientes` reads it, and its art. 60.3 grade, a judicial
    incapacity included, reaches the disability threshold. A row whose entitlement
    or grade is undecided is not counted; its unstated facts withhold the mínimo.
    """
    thresholds = _thresholds(context)
    positions: list[int] = []
    for position, ascendant in enumerate(ascendants, start=1):
        divisor = _entitlement(ascendant, filing_year, amounts=amounts, thresholds=thresholds)
        if isinstance(divisor, int) and divisor > 0 and ascendant.has_disability(thresholds.grades) is True:
            positions.append(position)
    return tuple(positions)


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
    condition holds: an age at the devengo of at least ``qualifying_age``, or an
    art. 60.3 grade of at least ``qualifying_discapacidad_grado``. It counts by the
    art. 61 norma 1ª share, one over the descendants entitled with the filer. A row
    a stated fact rules out, on either side, counts zero whatever else it omits; any
    other row that omits a deciding fact withholds the count, as it withholds the
    mínimo. The total is a weighted count of persons, not an amount.
    """
    thresholds = _thresholds(context)
    return _aggregate(
        [
            _weight(
                ascendant,
                filing_year,
                amounts=amounts,
                thresholds=thresholds,
                qualifying_age=qualifying_age,
                qualifying_discapacidad_grado=qualifying_discapacidad_grado,
            )
            for ascendant in ascendants
        ]
    )


__all__ = [
    "CONVIVENCIA_MITAD_PERIODO_LEAF",
    "CONVIVIENTES_LEAF",
    "DECLARACION_PROPIA_LEAF",
    "DISCAPACIDAD_ASISTENCIA_LEAF",
    "DISCAPACIDAD_LEAF",
    "INCAPACIDAD_JUDICIAL_LEAF",
    "RENTAS_ANUALES_LEAF",
    "AscendantDisabilityKey",
    "AscendantFactUnstated",
    "AscendantInfo",
    "AscendantMinimumAmounts",
    "AscendantMinimumResult",
    "DisabilityGrades",
    "ascendant_entitlement_weighted_count",
    "disability_minimum_positions",
    "minimo_ascendientes",
]
