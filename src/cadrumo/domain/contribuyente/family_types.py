"""Typed personal/family profile records for Modelo 100 inputs.

The records in this module describe factual people and family-unit flags.
They do not decide Modelo 100 legal treatment, minimum amounts, deduction
eligibility, or casilla formulas; those remain registry-owned.

:class:`DescendantInfo`, :class:`RentaDescendantProfile`, and
:class:`RentaAscendantProfile` feed :class:`RentaFamilyProfile`, whose helper
methods derive Art. 58 minimum counts and Art. 81 maternity/guardería amounts
from the factual profile records.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, NonNegativeInt, field_validator

from ...core.external_constants import (
    ART_81_1_ENTRY_WINDOW_YEARS as _ART_81_1_ENTRY_WINDOW_YEARS,
)
from ...core.external_constants import (
    MINIMO_DESCENDIENTE_MAX_AGE,
    MINIMO_MENOR_TRES_MAX_AGE,
)
from ...core.external_constants import (
    NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS as _NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS,
)
from ...core.identity import SubjectTaxId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.parsing import parse_iso8601_date
from ...core.text_bounds import CalendarMonth
from .errors import ProfileValidationError

# Comunidad de Madrid "Por nacimiento o adopción de hijos" deducción autonómica
# (DL 1/2010, de 21 octubre, arts. 4 y 18.1). Ámbito temporal: the deducción
# applies in the period of nacimiento/adopción AND in each of the two following
# periods. The figure itself lives beside its Art. 58 / Art. 61 siblings in the
# curated external-constants layer; the alias keeps internal call sites stable.
NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS = _NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS


def within_multi_year_applicability_window(
    entry_year: int,
    filing_year: int,
    *,
    following_periods: int,
) -> bool:
    """Return whether *filing_year* is inside a multi-year applicability window.

    A reusable primitive for autonomic deducciones that apply in the period of
    a triggering event (a nacimiento, an adopción, a rehabilitación, ...) plus a
    fixed number of following periods. The window is the closed interval
    ``[entry_year, entry_year + following_periods]``; ``following_periods = 0``
    yields a single-year window.

    Args:
        entry_year: Calendar year of the triggering event.
        filing_year: The filing year whose eligibility is being tested.
        following_periods: Count of periods after ``entry_year`` in which the
            deducción remains applicable. Must be non-negative.
    """
    if following_periods < 0:
        raise ProfileValidationError("following_periods must be non-negative")
    return entry_year <= filing_year <= entry_year + following_periods


# Art. 58 thresholds sourced from the central authority: age < 25 (exclusive)
# for ordinary mínimo eligibility, age < 3 (exclusive) for the bajo-3-años
# supplement. The module-private aliases keep the internal call sites stable.
MAX_AGE_ORDINARY = MINIMO_DESCENDIENTE_MAX_AGE
MAX_AGE_MENOR_TRES = MINIMO_MENOR_TRES_MAX_AGE

# Art. 81.1 LIRPF: the adopción/acogimiento limb runs "durante los tres años
# siguientes a la fecha de la inscripción en el Registro Civil". Counted in
# YEARS from a date, unlike the Art. 58.2 limb above, which counts whole tax
# PERIODS from the entry period — hence a separate constant rather than a reuse
# of the period count, which would read as the same rule and is not.
ART_81_1_ENTRY_WINDOW_YEARS = _ART_81_1_ENTRY_WINDOW_YEARS


def months_of_year_between(
    start: tuple[int, int],
    end: tuple[int, int],
    filing_year: int,
) -> frozenset[int]:
    """Months of *filing_year* inside the half-open ``(year, month)`` span ``[start, end)``.

    Compares ``(year, month)`` pairs rather than dates so a span anchored on a 29
    February event resolves in a non-leap year, where constructing the
    anniversary date raises. Half-open by design: both Art. 81.1 windows count
    their opening month in full and exclude the month the span runs out.
    """
    return frozenset(month for month in range(1, 13) if start <= (filing_year, month) < end)


def coerce_iso_date_field(value: object) -> object:
    """Delegate for @field_validator date fields: parse ISO strings, pass through everything else."""
    if isinstance(value, str):
        return parse_iso8601_date(value)
    return value


class MinimoDescendientesThresholds(BaseModel):
    """The two Art. 58.1 / Art. 61 norma 2ª eligibility figures, per filing year.

    Both are registry ``money`` parameters the caller resolves for the filing
    year being computed; this domain layer performs no euro-figure lookup of
    its own (`aeat-registry-authority-flow`). Carrying them as one required
    argument rather than two optional ones is deliberate: an optional threshold
    would let a caller silently skip half the law and inflate the mínimo, which
    is the exact defect this record exists to close.

    Fields
    ------
    rentas_anuales_limite
        Art. 58.1 LIRPF ceiling on the descendant's own annual rentas excluding
        exempt income. Registry parameter
        ``renta-{year}-minimo-descendientes-rentas-anuales-limite-{year}``.
    declaracion_propia_rentas_limite
        Art. 61 norma 2ª LIRPF ceiling on the rentas in a descendant's OWN
        return. Registry parameter
        ``renta-{year}-minimo-descendientes-declaracion-propia-rentas-limite-{year}``.
    """

    model_config = _STRICT_FROZEN

    rentas_anuales_limite: Decimal = Field(ge=Decimal("0"))
    declaracion_propia_rentas_limite: Decimal = Field(ge=Decimal("0"))


class GuarderiaMonthSpend(BaseModel):
    """One month's guardería spend for one descendant (Art. 81.2 LIRPF).

    Month-granular because the statute is: the increase runs while the child is
    under three and, in the period the child TURNS three, extends to the spend
    "incurridos con posterioridad al cumplimiento de dicha edad" up to the month
    before the second cycle of infant education may begin. An annual total
    cannot express either boundary.

    The map these build is SPARSE by construction — a month with no spend simply
    has no entry — so nothing here encodes a window. That is deliberate and is
    the whole reason the shape is monthly primaries rather than a pre-split
    figure: every split shape would bake a boundary into stored data, and the
    upper boundary is not this application's to determine.
    """

    model_config = _STRICT_FROZEN

    month: CalendarMonth
    amount_euros: NonNegativeInt


class _RentaPersonProfileBase(BaseModel):
    """Private base for person-profile rows in the official Modelo 100 family section.

    Carries the shared :class:`~datetime.date` fields and their validators for
    :class:`RentaDescendantProfile` and :class:`RentaAscendantProfile`.
    Both subclasses declare the same ``tax_id``/``display_name``/
    ``disability_grade`` optional-text guard and the ``birth_date``/
    ``death_date`` ISO-8601 parser; extracting them here removes the
    duplicate without altering any field constraint.
    """

    model_config = _STRICT_FROZEN

    tax_id: SubjectTaxId | None = None
    display_name: str | None = None
    birth_date: date
    disability_grade: str | None = None
    death_date: date | None = None

    @field_validator("tax_id", "display_name", "disability_grade")
    @classmethod
    def _optional_text_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ProfileValidationError("optional text fields must not be blank")
        return stripped

    @field_validator("birth_date", "death_date", mode="before")
    @classmethod
    def _parse_date(cls, value: object) -> object:
        return coerce_iso_date_field(value)


class RentaDescendantProfile(_RentaPersonProfileBase):
    """One descendant row from the official Modelo 100 family section."""


class RentaAscendantProfile(_RentaPersonProfileBase):
    """One ascendant row from the official Modelo 100 family section."""

    cohabiting_descendant_count: int | None = Field(default=None, ge=0, le=10)
