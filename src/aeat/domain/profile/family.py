"""Typed personal/family profile records for Modelo 100 inputs.

The records in this module describe factual people and family-unit flags.
They do not decide Modelo 100 legal treatment, minimum amounts, deduction
eligibility, or casilla formulas; those remain registry-owned.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._errors import ProfileValidationError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

# Art. 58.1 LIRPF: first-child cutoff for full-year eligibility is 1 July.
_FULL_YEAR_CUTOFF_MONTH = 7
_FULL_YEAR_CUTOFF_DAY = 1

# Art. 58 thresholds: age < 25 (exclusive) for ordinary mínimo eligibility,
# age < 3 (exclusive) for the bajo-3-años supplement.
_MAX_AGE_ORDINARY = 25
_MAX_AGE_MENOR_TRES = 3


class DescendantInfo(BaseModel):
    """Structured per-descendant data for Art. 58 mínimo-por-descendientes.

    This record drives the mínimo-por-descendientes calculation (casilla 0513)
    and the bajo-3-años supplement (Art. 58.3).  It is intentionally richer
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
        Art. 59 LIRPF: when ``True``, both progenitors share custody under a
        judicial or administrative arrangement. The mínimo-por-descendientes
        and the bajo-3-años supplement for this child are split 50 % between
        them (Art. 59 prorrata). Default ``False`` (sole custody / not
        applicable). Setting this flag on a non-cohabiting descendant has no
        additional effect because eligibility already fails.
    nif
        Optional NIF/NIE; validated for shape when present.
    """

    model_config = _STRICT_FROZEN

    birth_date: date
    adoption_date: date | None = None
    discapacidad_grado: Literal[0, 33, 65] | None = None
    convive_con_contribuyente: bool = True
    custodia_compartida: bool = False
    nif: str | None = None

    @field_validator("birth_date", "adoption_date", mode="before")
    @classmethod
    def _parse_date(cls, value: object) -> object:
        if isinstance(value, str):
            return date.fromisoformat(value)
        return value

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
                f"adoption_date {self.adoption_date} must not be in the future (today={today})"
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
        """True when the descendant qualifies for the Art. 58.3 bajo-3-años supplement."""
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


class RentaDescendantProfile(BaseModel):
    """One descendant row from the official Modelo 100 family section."""

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
        if isinstance(value, str):
            return date.fromisoformat(value)
        return value


class RentaAscendantProfile(BaseModel):
    """One ascendant row from the official Modelo 100 family section."""

    model_config = _STRICT_FROZEN

    tax_id: str | None = None
    display_name: str | None = None
    birth_date: date
    disability_grade: str | None = None
    cohabiting_descendant_count: int | None = Field(default=None, ge=0, le=10)
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
        if isinstance(value, str):
            return date.fromisoformat(value)
        return value


class RentaFamilyProfile(BaseModel):
    """Typed repeated family-member facts consumed by Modelo 100 bindings."""

    model_config = _STRICT_FROZEN

    schema_version: str = Field(default="1")
    descendants: tuple[RentaDescendantProfile, ...] = ()
    ascendants: tuple[RentaAscendantProfile, ...] = ()
    descendientes: tuple[DescendantInfo, ...] = ()
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
        """Count of eligible descendientes whose age at year-end < 3 (Art. 58.3)."""
        return sum(1 for d in self.descendientes if d.is_eligible_menor_tres(filing_year))

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
        return sum(
            1
            for d in self.descendientes
            if d.custodia_compartida and d.is_eligible_ordinary(filing_year)
        )

    def custodia_compartida_prorrata_factor(self, descendant: "DescendantInfo", filing_year: int) -> "Decimal":
        """Return the Art. 59 LIRPF prorrata factor for one descendant.

        Returns ``Decimal("0.5")`` when ``descendant.custodia_compartida`` is
        ``True`` and the descendant is eligible for the mínimo, otherwise
        ``Decimal("1")``.
        """
        from decimal import Decimal

        if descendant.custodia_compartida and descendant.is_eligible_ordinary(filing_year):
            return Decimal("0.5")
        return Decimal("1")

    def custodia_compartida_advisory(self, filing_year: int) -> str | None:
        """Return the translated Art. 59 prorrata advisory string, or ``None``.

        When at least one eligible descendant has ``custodia_compartida=True``
        the returned string reads "Se ha aplicado prorrata 50 % (Art. 59 LIRPF)
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


__all__ = [
    "DescendantInfo",
    "RentaAscendantProfile",
    "RentaDescendantProfile",
    "RentaFamilyProfile",
]
