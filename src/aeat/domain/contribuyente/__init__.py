"""The operator's tax-residence profile.

This package is intentionally separate from financial usage-ratio
profiles, browser profiles, and spending-category profiles. It owns
personal local state needed to parameterize RENTA verification.

:class:`TaxResidenceProfile` and :class:`ResidenceChange` carry the
:class:`~aeat.domain.contribuyente._ccaa.CCAA` residence axis; :class:`RentaFamilyProfile` and
:class:`DescendantInfo` carry the Modelo 100 personal/family facts, and
:class:`ProfileKey` exposes the wizard-registered editable profile schema.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unicodedata import category, normalize

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.parsing._dates import _parse_iso8601_date
from ._ccaa import CCAA
from ._constants import ProfileName
from ._errors import ForalRegimeError, ProfileNotConfiguredError, ProfileValidationError, TaxResidenceProfileError
from ._keys import (
    ProfileKey,
    ProfileKeyRequirement,
    get_profile_key,
    optional_profile_keys,
    required_profile_keys,
)
from ._marriage_facts import (
    marriage_date_from_facts,
    marriage_derived_facts,
    marriage_full_year,
    marriage_month_start,
    parse_marriage_date_flag,
)
from ._normalise import normalise_key
from ._renta_codes import (
    UE_EEA_COUNTRY_CODES,
    RentaDeclaracionType,
    RentaDisabilityGrade,
    RentaMaritalStatus,
    RentaSexCode,
    SituacionFamiliar,
    SituacionFamiliarM145,
)
from .family import DescendantInfo, RentaAscendantProfile, RentaDescendantProfile, RentaFamilyProfile

if TYPE_CHECKING:
    # ``PROFILE_KEYS`` is defined lazily via ``__getattr__`` below so the
    # wizard catalogue (the source of truth) can import the leaf modules
    # under ``aeat.domain.contribuyente`` without triggering the catalogue-driven
    # build. Type checkers see the same tuple-of-``ProfileKey`` contract as
    # an eager export would expose.
    from ._keys import PROFILE_KEYS as PROFILE_KEYS


def __getattr__(name: str) -> tuple[ProfileKey, ...]:
    """Lazily resolve ``PROFILE_KEYS`` so the wizard catalogue can import first."""
    if name == "PROFILE_KEYS":
        from ._keys import PROFILE_KEYS

        return PROFILE_KEYS
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_FORAL_ALIASES = frozenset(
    {
        "pais-vasco",
        "país-vasco",
        "pais_vasco",
        "país_vasco",
        "euskadi",
        "navarra",
    },
)


class ResidenceChange(BaseModel, frozen=True, strict=True):
    """One historic tax-residence transition."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    from_ccaa: CCAA | None
    to_ccaa: CCAA
    effective_from: date
    reason: str | None = None

    @field_validator("from_ccaa", "to_ccaa", mode="before")
    @classmethod
    def _parse_ccaa(cls, value: object) -> object:
        if isinstance(value, str):
            return parse_tax_region(value)
        return value

    @field_validator("effective_from", mode="before")
    @classmethod
    def _parse_effective_from(cls, value: object) -> object:
        if isinstance(value, str):
            return _parse_iso8601_date(value)
        return value


class TaxResidenceProfile(BaseModel, frozen=True, strict=True):
    """The operator's current ordinary CCAA tax residence for RENTA."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default="1")
    ccaa: CCAA
    tax_residence_since: date | None = None
    tax_residence_change_history: tuple[ResidenceChange, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_is_supported(cls, value: str) -> str:
        if value != "1":
            raise ProfileValidationError("schema_version must be '1'")
        return value

    @field_validator("ccaa", mode="before")
    @classmethod
    def _parse_ccaa(cls, value: object) -> object:
        if isinstance(value, str):
            return parse_tax_region(value)
        return value

    @field_validator("tax_residence_change_history", mode="before")
    @classmethod
    def _parse_change_history(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @field_validator("tax_residence_since", mode="before")
    @classmethod
    def _parse_since(cls, value: object) -> object:
        if isinstance(value, str):
            return _parse_iso8601_date(value)
        return value


def parse_tax_region(raw: str) -> CCAA:
    """Parse a CLI/user tax-region token into the closed :class:`~aeat.domain.contribuyente._ccaa.CCAA` enum."""
    normalized = _normalize_region_token(raw)
    if normalized in _FORAL_ALIASES:
        raise ForalRegimeError(raw)
    try:
        return CCAA(normalized)
    except ValueError as exc:
        valid = ", ".join(sorted(ccaa.value for ccaa in CCAA))
        raise TaxResidenceProfileError(
            f"unknown tax-region {raw!r}; valid CCAA values: {valid}",
            context={"tax_region": raw},
            suggestion="aeat config profile edit NAME --tax-residence-ccaa <ccaa>",
        ) from exc


def _normalize_region_token(raw: str) -> str:
    stripped = raw.strip().lower().replace(" ", "_").replace("-", "_")
    decomposed = normalize("NFD", stripped)
    return "".join(char for char in decomposed if category(char) != "Mn")


__all__ = [
    "CCAA",
    "PROFILE_KEYS",
    "UE_EEA_COUNTRY_CODES",
    "DescendantInfo",
    "ForalRegimeError",
    "ProfileKey",
    "ProfileKeyRequirement",
    "ProfileName",
    "ProfileNotConfiguredError",
    "ProfileValidationError",
    "RentaAscendantProfile",
    "RentaDeclaracionType",
    "RentaDescendantProfile",
    "RentaDisabilityGrade",
    "RentaFamilyProfile",
    "RentaMaritalStatus",
    "RentaSexCode",
    "ResidenceChange",
    "SituacionFamiliar",
    "SituacionFamiliarM145",
    "TaxResidenceProfile",
    "TaxResidenceProfileError",
    "get_profile_key",
    "marriage_date_from_facts",
    "marriage_derived_facts",
    "marriage_full_year",
    "marriage_month_start",
    "normalise_key",
    "optional_profile_keys",
    "parse_marriage_date_flag",
    "parse_tax_region",
    "required_profile_keys",
]
