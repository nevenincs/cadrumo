"""Kent's tax-residence profile.

This package is intentionally separate from financial usage-ratio
profiles, browser profiles, and spending-category profiles. It owns
personal local state needed to parameterize RENTA verification.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..formulas._rulesets.modelo_100._ccaa import CCAA
from ._errors import ForalRegimeError, ProfileNotConfiguredError, TaxResidenceProfileError
from ._storage import clear_json, default_path, load_json, save_json

_FORAL_ALIASES = frozenset(
    {
        "pais-vasco",
        "país-vasco",
        "pais_vasco",
        "país_vasco",
        "euskadi",
        "navarra",
    }
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
            return date.fromisoformat(value)
        return value


class KentTaxResidence(BaseModel, frozen=True, strict=True):
    """Kent's current ordinary CCAA tax residence for RENTA."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default="1")
    ccaa: CCAA
    tax_residence_since: date | None = None
    tax_residence_change_history: tuple[ResidenceChange, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_is_supported(cls, value: str) -> str:
        if value != "1":
            raise ValueError("schema_version must be '1'")
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
            return date.fromisoformat(value)
        return value


def parse_tax_region(raw: str) -> CCAA:
    """Parse a CLI/user tax-region token into the closed ``CCAA`` enum."""

    normalized = raw.strip().lower().replace(" ", "_")
    if normalized in _FORAL_ALIASES:
        raise ForalRegimeError(raw)
    try:
        return CCAA(normalized)
    except ValueError as exc:
        valid = ", ".join(sorted(ccaa.value for ccaa in CCAA))
        raise TaxResidenceProfileError(
            f"unknown tax-region {raw!r}; valid CCAA values: {valid}",
            context={"tax_region": raw},
            suggestion="aeat profile set tax-region <ccaa>",
        ) from exc


def load_tax_residence(path: object | None = None) -> KentTaxResidence | None:
    """Load Kent's tax-residence profile, returning ``None`` if absent."""

    payload = load_json(_coerce_path(path))
    if payload is None:
        return None
    try:
        return KentTaxResidence.model_validate(payload)
    except ValidationError as exc:
        raise TaxResidenceProfileError("invalid tax-residence profile content") from exc


def require_tax_residence(path: object | None = None) -> KentTaxResidence:
    """Load Kent's tax-residence profile or raise a REFUSED error."""

    residence = load_tax_residence(path)
    if residence is None:
        raise ProfileNotConfiguredError()
    return residence


def save_tax_residence(residence: KentTaxResidence, path: object | None = None) -> None:
    """Persist Kent's tax-residence profile as schema-versioned JSON."""

    save_json(residence.model_dump(mode="json"), _coerce_path(path))


def clear_tax_residence(path: object | None = None) -> None:
    """Delete Kent's tax-residence profile if it exists."""

    clear_json(_coerce_path(path))


def _coerce_path(path: object | None):
    if path is None:
        return None
    from pathlib import Path

    if isinstance(path, Path):
        return path
    if isinstance(path, str):
        return Path(path)
    return path  # let storage/type checking fail loudly


__all__ = [
    "CCAA",
    "ForalRegimeError",
    "KentTaxResidence",
    "ProfileNotConfiguredError",
    "ResidenceChange",
    "TaxResidenceProfileError",
    "clear_tax_residence",
    "default_path",
    "load_tax_residence",
    "parse_tax_region",
    "require_tax_residence",
    "save_tax_residence",
]
