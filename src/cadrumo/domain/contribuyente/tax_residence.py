"""Where a taxpayer is tax-resident, and how that has changed.

These models and the region parser were defined directly in the package
namespace, which is why deleting an export map could not make it inert.
They live in a module of their own now.
"""

from __future__ import annotations

from datetime import date
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.parsing.dates import parse_iso8601_date as _parse_iso8601_date
from ...core.text_fold import fold_diacritics as _fold_diacritics
from .ccaa import CCAA
from .constants import SUPPORTED_PROFILE_SCHEMA_VERSION, ProfileSchemaVersion
from .errors import ForalRegimeError, TaxResidenceProfileError

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

    schema_version: ProfileSchemaVersion = Field(default=SUPPORTED_PROFILE_SCHEMA_VERSION)
    ccaa: CCAA
    tax_residence_since: date | None = None
    tax_residence_change_history: tuple[ResidenceChange, ...] = ()

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
            # CAST-RATIONALE-TAX-RESIDENCE-CHANGE-HISTORY: isinstance narrows to
            # list but not its element type; pydantic re-validates each element
            # against the field's declared item type after this coercion.
            # nosemgrep: no-cast-in-domain-application
            return tuple(cast(list[object], value))
        return value

    @field_validator("tax_residence_since", mode="before")
    @classmethod
    def _parse_since(cls, value: object) -> object:
        if isinstance(value, str):
            return _parse_iso8601_date(value)
        return value


def parse_tax_region(raw: str) -> CCAA:
    """Parse a CLI/user tax-region token into the closed :class:`CCAA` enum."""
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
        ) from exc


def _normalize_region_token(raw: str) -> str:
    stripped = raw.strip().casefold().replace(" ", "_").replace("-", "_")
    return _fold_diacritics(stripped)
