"""Strict pydantic v2 records for config profiles."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..workflow._utils import _normalise_key, utc_now


class ProfileRecord(BaseModel):
    """Config profile values entered by the user."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    values: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("profile name must not be blank")
        return trimmed

    @field_validator("values")
    @classmethod
    def _normalise_values(cls, value: dict[str, str]) -> dict[str, str]:
        return {_normalise_key(str(key)): str(raw).strip() for key, raw in value.items()}
