"""Strict records describing editable application profile keys.

The setup wizard owns the questions that produce these records.  This module
owns only the record shape and its local invariants; catalogue resolution
lives in :mod:`cadrumo.application.user_profile.profile_keys`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.i18n.translatable import Translatable as tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.requirement import Requirement
from ...domain.contribuyente.errors import ProfileValidationError


class ProfileKey(BaseModel):
    """Strict frozen record describing one editable profile key."""

    model_config = STRICT_FROZEN_CONFIG

    key: str = Field(min_length=1, max_length=128)
    requirement: Requirement
    description: tr
    required_when_key: str | None = None
    required_when_value: str | None = None

    @field_validator("key")
    @classmethod
    @pydantic_validation_boundary
    def _validate_key_shape(cls, value: str) -> str:
        """Reject blank or whitespace-padded keys; keep dot-separated paths intact."""
        if not value.strip():
            raise ProfileValidationError("key must not be empty or whitespace-only")
        if value.strip() != value:
            raise ProfileValidationError("key must not be padded with whitespace")
        return value

    @field_validator("description")
    @classmethod
    @pydantic_validation_boundary
    def _validate_description_key(cls, value: tr) -> tr:
        """Require profile-owned translation keys for authoritative descriptions."""
        if not value.strip():
            raise ProfileValidationError("description must not be empty")
        if not str(value).startswith("profile.keys."):
            raise ProfileValidationError("description must use a profile translation key")
        return value

    @field_validator("required_when_key", "required_when_value")
    @classmethod
    @pydantic_validation_boundary
    def _validate_conditional_requirement(cls, value: str | None) -> str | None:
        """Reject blank or padded conditional requirement values."""
        if value and value.strip() != value:
            raise ProfileValidationError("conditional requirement fields must not be padded")
        if value == "":
            raise ProfileValidationError("conditional requirement fields must not be empty")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_conditional_requirement_pair(self) -> ProfileKey:
        """Require both halves of a conditional requirement together."""
        if bool(self.required_when_key) != bool(self.required_when_value):
            raise ProfileValidationError("required_when_key and required_when_value must be set together")
        return self


__all__ = ["ProfileKey"]
