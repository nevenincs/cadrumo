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
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import (
    CUSTODIA_COMPARTIDA_PRORRATA_FACTOR,
    DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR,
    DEDUCCION_MATERNIDAD_MENSUAL_EUR,
    INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR,
    MINIMO_DESCENDIENTE_MAX_AGE,
    MINIMO_MENOR_TRES_MAX_AGE,
)
from ...core.parsing._dates import _parse_iso8601_date
from ._errors import ProfileValidationError

# Art. 58.1 LIRPF: first-child cutoff for full-year eligibility is 1 July.
_FULL_YEAR_CUTOFF_MONTH = 7
_FULL_YEAR_CUTOFF_DAY = 1

# Art. 58 thresholds sourced from the central authority: age < 25 (exclusive)
# for ordinary mínimo eligibility, age < 3 (exclusive) for the bajo-3-años
# supplement. The module-private aliases keep the internal call sites stable.
_MAX_AGE_ORDINARY = MINIMO_DESCENDIENTE_MAX_AGE
_MAX_AGE_MENOR_TRES = MINIMO_MENOR_TRES_MAX_AGE


def _coerce_iso_date_field(value: object) -> object:
    """Delegate for @field_validator date fields: parse ISO strings, pass through everything else."""
    if isinstance(value, str):
        return _parse_iso8601_date(value)
    return value


class DescendantInfo(BaseModel):
    """Structured per-descendant data for Art. 58 mínimo-por-descendientes.

    This record drives the mínimo-por-descendientes calculation (casilla 0513)
    and the bajo-3-años supplement (Art. 58.2).  It is intentionally richer
    than :class:`RentaDescendantProfile`, which models official-form rows.

    Fields
    ------
    birth_date
        Required date of birth.
    adoption_date
        Finalisation date of the adoption, or ``None`` for a biological child.
        When present it must be ≥ ``birth_date`` and ≤ today.
    discapacidad_grado
        0 = sin discapacidad, 33 = grado ≥ 33 % < 65 %, 65 = grado ≥ 65 %.
        A disabled descendant remains mínimo-eligible regardless of age.
    convive_con_contribuyente
        Whether the descendant cohabits with the taxpayer (Art. 58.1 condition).
    custodia_compartida
        Art. 61 LIRPF: when ``True``, both progenitors share custody under a
        judicial or administrative arrangement. The mínimo-por-descendientes
        and the bajo-3-años supplement for this child are split 50 % between
        them (Art. 61 prorrata). Default ``False`` (sole custody / not
        applicable). Setting this flag on a non-cohabiting descendant has no
        additional effect because eligibility already fails.
    meses_madre_trabajo_2024
        Months the mother worked while this child was under 3 years old during
        the 2024 filing year.  Used by Art. 81 LIRPF deducción maternidad:
        ``min(meses × 100, 1_200)`` per eligible child.  Valid range: 0–12.
        Default ``0`` (no deducción contribution from this child).
    gastos_guarderia_euros
        Actual guardería / centro educación infantil autorizado expenses paid
        for this child (Art. 81 bis LIRPF).  Integer euros, ≥ 0.
        Default ``0`` (no guardería expenses declared for this child).
    nif
        Optional NIF/NIE; validated for shape when present.
    """

    model_config = _STRICT_FROZEN

    birth_date: date
    adoption_date: date | None = None
    discapacidad_grado: Literal[0, 33, 65] | None = None
    convive_con_contribuyente: bool = True
    custodia_compartida: bool = False
    meses_madre_trabajo_2024: int = Field(default=0, ge=0, le=12)
    gastos_guarderia_euros: int = Field(default=0, ge=0)
    nif: str | None = None

    @field_validator("birth_date", "adoption_date", mode="before")
    @classmethod
    def _parse_date(cls, value: object) -> object:
        return _coerce_iso_date_field(value)

    @field_validator("nif")
    @classmethod
    def _validate_nif(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().upper()
        if not stripped:
            raise ProfileValidationError("nif must not be blank when provided")
        if len(stripped) not in (9,):
            raise ProfileValidationError(f"nif must be 9 characters, got {len(stripped)!r} for {value!r}")
        return stripped

    @model_validator(mode="after")
    def _validate_adoption_date(self) -> DescendantInfo:
        if self.adoption_date is None:
            return self
        if self.adoption_date < self.birth_date:
            raise ProfileValidationError(f"adoption_date {self.adoption_date} must be ≥ birth_date {self.birth_date}")
        today = date.today()
        if self.adoption_date > today:
            raise ProfileValidationError(
                f"adoption_date {self.adoption_date} must not be in the future (today={today})",
            )
        return self

    def age_at_year_end(self, filing_year: int) -> int:
        """Return the descendant's age on 31 December of *filing_year*."""
        year_end = date(filing_year, 12, 31)
        age = year_end.year - self.birth_date.year
        # Subtract one if the birthday has not yet occurred by year-end.
        if (self.birth_date.month, self.birth_date.day) > (year_end.month, year_end.day):
            age -= 1
        return age

    def _entry_date(self) -> date:
        """The effective entry date used for prorrata: adoption or birth."""
        return self.adoption_date if self.adoption_date is not None else self.birth_date

    def is_eligible_ordinary(self, filing_year: int) -> bool:
        """True when the descendant qualifies for the Art. 58.1 ordinary mínimo.

        Eligibility: age < 25 at year-end OR any degree of discapacidad, AND
        cohabiting with the taxpayer.
        """
        if not self.convive_con_contribuyente:
            return False
        if self.discapacidad_grado and self.discapacidad_grado > 0:
            return True
        return self.age_at_year_end(filing_year) < _MAX_AGE_ORDINARY

    def is_eligible_menor_tres(self, filing_year: int) -> bool:
        """True when the descendant qualifies for the Art. 58.2 bajo-3-años supplement."""
        if not self.convive_con_contribuyente:
            return False
        return self.age_at_year_end(filing_year) < _MAX_AGE_MENOR_TRES

    def joined_before_or_on_1_july(self, filing_year: int) -> bool:
        """True when entry (birth or adoption) falls before 1 July of *filing_year*.

        Used by Art. 58.4 prorrata: a descendant born / adopted before 1 July
        counts for the full year. One born on or after 1 July counts half-year.
        """
        entry = self._entry_date()
        if entry.year < filing_year:
            return True
        if entry.year > filing_year:
            return False
        return (entry.month, entry.day) < (_FULL_YEAR_CUTOFF_MONTH, _FULL_YEAR_CUTOFF_DAY)


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

    tax_id: str | None = None
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
        return _coerce_iso_date_field(value)


class RentaDescendantProfile(_RentaPersonProfileBase):
    """One descendant row from the official Modelo 100 family section."""


class RentaAscendantProfile(_RentaPersonProfileBase):
    """One ascendant row from the official Modelo 100 family section."""

    cohabiting_descendant_count: int | None = Field(default=None, ge=0, le=10)


class RentaFamilyProfile(BaseModel):
    """Typed repeated family-member facts consumed by Modelo 100 bindings."""

    model_config = _STRICT_FROZEN

    schema_version: str = Field(default="1")
    descendants: tuple[RentaDescendantProfile, ...] = ()
    ascendants: tuple[RentaAscendantProfile, ...] = ()
    descendientes: tuple[DescendantInfo, ...] = ()
    cotizaciones_ss_madre_2024: int = Field(default=0, ge=0)
    """SS cotizaciones paid by the mother during 2024 (mirrors casilla 0013).

    Used as the statutory cap for the Art. 81 bis guardería incremento:
    0613 = min(gastos_guarderia_reales, hijos_menores_3 × 1000, cotizaciones_ss_madre_2024).
    Default ``0`` (cap not declared; guardería incremento will be zero).
    """
    """Structured per-descendant data for Art. 58 mínimo calculation.

    Each entry carries birth / adoption date, discapacidad grade, and
    cohabitation flag.  The ``descendants`` tuple above models the
    official Modelo 100 form rows; this tuple drives the mínimo engine.
    """

    @field_validator("schema_version")
    @classmethod
    def _schema_version_is_supported(cls, value: str) -> str:
        if value != "1":
            raise ProfileValidationError("schema_version must be '1'")
        return value

    @field_validator("descendants", "ascendants", mode="before")
    @classmethod
    def _tuple_from_list(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @field_validator("descendientes", mode="before")
    @classmethod
    def _descendientes_from_list(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    # ------------------------------------------------------------------
    # Derived properties for Art. 58 mínimo-por-descendientes
    # ------------------------------------------------------------------

    @property
    def descendientes_count(self) -> int:
        """Total number of DescendantInfo entries."""
        return len(self.descendientes)

    def descendientes_menores_3_year_end(self, filing_year: int) -> int:
        """Count of eligible descendientes whose age at year-end < 3 (Art. 58.2)."""
        return sum(1 for d in self.descendientes if d.is_eligible_menor_tres(filing_year))

    @property
    def descendientes_menores_3_2024(self) -> int:
        """Count of descendants eligible for the bajo-3-años supplement in 2024.

        Binding-compatible property (no argument) for the 2024 registry binding
        ``renta-2024-profile-descendientes-menores-3``.
        """
        return self.descendientes_menores_3_year_end(2024)

    @property
    def gastos_guarderia_reales_2024(self) -> int:
        """Sum of Art. 81 bis guardería expenses across eligible children under 3 in 2024.

        Only children eligible for the bajo-3-años supplement (age < 3 at
        year-end 2024 AND cohabiting) contribute their ``gastos_guarderia_euros``.
        Used as the ``gastos_reales`` term in the 0613 formula:
        min(gastos_guarderia_reales_2024, descendientes_menores_3_2024 × 1000,
        cotizaciones_ss_madre_2024).
        """
        return sum(d.gastos_guarderia_euros for d in self.descendientes if d.is_eligible_menor_tres(2024))

    def descendientes_eligible_minimum(self, filing_year: int) -> int:
        """Count of descendientes eligible for the ordinary Art. 58.1 mínimo.

        A descendant is eligible when age < 25 at year-end OR discapacidad > 0,
        and cohabiting with the taxpayer.
        """
        return sum(1 for d in self.descendientes if d.is_eligible_ordinary(filing_year))

    def descendientes_full_year_minimum(self, filing_year: int) -> int:
        """Count of eligible descendientes who joined before 1 July (full-year prorrata).

        Used by Art. 58.4 prorrata: descendants born / adopted before 1 July
        attract the full annual amount; those born on or after 1 July attract
        the half-year amount (50 %).
        """
        return sum(
            1
            for d in self.descendientes
            if d.is_eligible_ordinary(filing_year) and d.joined_before_or_on_1_july(filing_year)
        )

    def custodia_compartida_count(self, filing_year: int) -> int:
        """Count of eligible descendientes with custodia_compartida=True.

        Only eligible (Art. 58.1) and cohabiting descendants are counted;
        non-eligible ones carry no mínimo, so the prorrata has no effect.
        """
        return sum(1 for d in self.descendientes if d.custodia_compartida and d.is_eligible_ordinary(filing_year))

    def custodia_compartida_prorrata_factor(self, descendant: DescendantInfo, filing_year: int) -> Decimal:
        """Return the Art. 61 LIRPF prorrata factor for one descendant.

        Returns :data:`CUSTODIA_COMPARTIDA_PRORRATA_FACTOR` (``0.5``, Art. 61
        LIRPF) when ``descendant.custodia_compartida`` is ``True`` and the
        descendant is eligible for the mínimo, otherwise ``Decimal("1")``.
        """
        if descendant.custodia_compartida and descendant.is_eligible_ordinary(filing_year):
            return CUSTODIA_COMPARTIDA_PRORRATA_FACTOR
        return Decimal("1")

    def custodia_compartida_advisory(self, filing_year: int) -> str | None:
        """Return the translated Art. 61 prorrata advisory string, or ``None``.

        When at least one eligible descendant has ``custodia_compartida=True``
        the returned string reads "Se ha aplicado prorrata 50 % (Art. 61 LIRPF)
        por custodia compartida en X descendientes."  Returns ``None`` when no
        prorrata is in effect.
        """
        from ...core.i18n import tr

        count = self.custodia_compartida_count(filing_year)
        if count > 0:
            return tr(
                "profile.descendiente.custodia_compartida_prorrata_applied",
                count=count,
            )
        return None

    # ------------------------------------------------------------------
    # Art. 81 LIRPF deducción maternidad (casilla 0611)
    # ------------------------------------------------------------------

    def deduccion_maternidad_0611(self, filing_year: int) -> int:
        """Compute the Art. 81 LIRPF deducción maternidad for casilla 0611.

        Formula: ``sum(min(meses_madre_trabajo_2024 × 100, 1_200))`` for each
        descendant that is eligible for the bajo-3-años supplement (age < 3 at
        year-end AND cohabiting with the taxpayer).

        Returns an integer euros amount (casilla 0611 carries no decimal places
        on the official form).  Returns ``0`` when no eligible child has a
        non-zero ``meses_madre_trabajo_2024``.
        """
        total = 0
        for d in self.descendientes:
            if d.is_eligible_menor_tres(filing_year) and d.meses_madre_trabajo_2024 > 0:
                total += min(
                    d.meses_madre_trabajo_2024 * DEDUCCION_MATERNIDAD_MENSUAL_EUR,
                    DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR,
                )
        return total

    # ------------------------------------------------------------------
    # Art. 81 LIRPF guardería incremento (casilla 0613)
    # ------------------------------------------------------------------

    def incremento_guarderia_0613(self, filing_year: int) -> int:
        """Compute the Art. 81 LIRPF guardería incremento for casilla 0613.

        Formula (Art. 81 LIRPF — incremento por gastos de custodia en guardería,
        NOT Art. 81 bis which covers familia numerosa / discapacidad)::

            min(gastos_guarderia_reales,
                hijos_menores_3 × INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR,
                cotizaciones_ss_madre_2024)

        Only the 2024 filing year is supported by the profile fields
        (``gastos_guarderia_euros`` and ``cotizaciones_ss_madre_2024``); for
        other years, returns 0.

        Returns an integer euros amount.  Returns 0 when no eligible child has
        ``gastos_guarderia_euros > 0`` or ``cotizaciones_ss_madre_2024 == 0``.
        """
        if filing_year != 2024:
            return 0
        gastos_reales = self.gastos_guarderia_reales_2024
        hijos_menores_3 = self.descendientes_menores_3_2024
        cotizaciones = self.cotizaciones_ss_madre_2024
        if gastos_reales == 0 or hijos_menores_3 == 0 or cotizaciones == 0:
            return 0
        return min(gastos_reales, hijos_menores_3 * INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR, cotizaciones)

    def incremento_guarderia_advisory(self, filing_year: int) -> str | None:
        """Return a translated advisory string when 0613 can be auto-populated.

        Returns ``None`` when the incremento is zero.
        """
        from ...core.i18n import tr

        amount = self.incremento_guarderia_0613(filing_year)
        if amount > 0:
            return tr(
                "profile.descendiente.incremento_guarderia_applied",
                amount=amount,
            )
        return None

    def deduccion_maternidad_advisory(self, filing_year: int) -> str | None:
        """Return a translated advisory string when 0611 can be auto-populated.

        Returns ``None`` when no descendant under 3 carries
        ``meses_madre_trabajo_2024 > 0``, i.e. the computation produces zero.
        """
        from ...core.i18n import tr

        amount = self.deduccion_maternidad_0611(filing_year)
        if amount > 0:
            return tr(
                "profile.descendiente.deduccion_maternidad_applied",
                amount=amount,
            )
        return None


__all__ = [
    "DescendantInfo",
    "RentaAscendantProfile",
    "RentaDescendantProfile",
    "RentaFamilyProfile",
]
