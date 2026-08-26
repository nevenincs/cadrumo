"""Generic source identity attached to one row-binding coordinate."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from cadrumo.domain.calculations.registry.ids import BindingId

from ...core import STRICT_FROZEN_HIDDEN_INPUT_CONFIG, BindingSourceKind
from ...core.identity import ContentDigest

RowBindingKey = tuple[BindingId, int]
OpaqueSourceRowIdentity = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class RowSourceIdentity(BaseModel):
    """Opaque, fingerprinted identity of a source row.

    ``row_set_grouping`` retains the exact registry row-set selector grouping
    when a row identity originates from that coordinate. It is optional because
    not every row identity originates from a registry row-set selector.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    source_kind: BindingSourceKind
    source_row_identity: OpaqueSourceRowIdentity = Field(repr=False)
    fingerprint: ContentDigest
    row_set_grouping: str | None = Field(default=None, min_length=1, max_length=128, repr=False)

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

    @field_validator("row_set_grouping")
    @classmethod
    def _row_set_grouping_is_canonical(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("row set grouping is not canonical")
        return value


__all__ = ["OpaqueSourceRowIdentity", "RowBindingKey", "RowSourceIdentity"]
