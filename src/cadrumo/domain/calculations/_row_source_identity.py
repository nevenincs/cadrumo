"""Generic source identity attached to one row-binding coordinate."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind
from ...core.identity import ContentDigest
from .registry import BindingId

RowBindingKey = tuple[BindingId, int]
OpaqueSourceRowIdentity = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class RowSourceIdentity(BaseModel):
    """Opaque, fingerprinted identity of a source row."""

    model_config = ConfigDict(**{**STRICT_FROZEN_CONFIG, "hide_input_in_errors": True})

    source_kind: BindingSourceKind
    source_row_identity: OpaqueSourceRowIdentity = Field(repr=False)
    fingerprint: ContentDigest

    @field_validator("source_kind", mode="before")
    @classmethod
    def _coerce_known_source_kind(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return BindingSourceKind(value)
            except ValueError:
                return value
        return value

    @field_validator("source_row_identity")
    @classmethod
    def _identity_is_canonical(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("row source identity is not canonical")
        return value


__all__ = ["OpaqueSourceRowIdentity", "RowBindingKey", "RowSourceIdentity"]
