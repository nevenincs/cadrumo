"""Typed personal/family profile records for Modelo 100 inputs.

The records in this module describe factual people and family-unit flags.
They do not decide Modelo 100 legal treatment, minimum amounts, deduction
eligibility, or casilla formulas; those remain registry-owned.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


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
            raise ValueError("optional text fields must not be blank")
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
            raise ValueError("optional text fields must not be blank")
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

    @field_validator("schema_version")
    @classmethod
    def _schema_version_is_supported(cls, value: str) -> str:
        if value != "1":
            raise ValueError("schema_version must be '1'")
        return value

    @field_validator("descendants", "ascendants", mode="before")
    @classmethod
    def _tuple_from_list(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value


__all__ = [
    "RentaAscendantProfile",
    "RentaDescendantProfile",
    "RentaFamilyProfile",
]
