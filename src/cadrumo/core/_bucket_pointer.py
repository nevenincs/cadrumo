"""Strict current-only record for the active-profile pointer.

The pointer is one durable, plaintext coordination record under the storage
root. It names either a selected bucket or an explicit absence and carries the
monotonic transition coordinate used by every pointer consumer. The record is
not a profile manifest or a profile-lifecycle assertion: it only records the
currently selected bucket.
"""

from __future__ import annotations

import tomllib
from typing import Final, Literal

from pydantic import BaseModel, Field, model_validator

from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .identity import BucketId

POINTER_SCHEMA_VERSION: Final[Literal[2]] = 2


class BucketPointer(BaseModel):
    """One strict active-profile selection and its durable transition revision.

    ``selection`` is deliberately explicit because TOML has no null scalar.
    A selected record carries exactly one bucket id; an absent record is the
    persisted tombstone written by clear. The physically absent initial file
    observes as an absent record at revision zero and is never accepted as an
    on-disk compatibility format.
    """

    model_config = _STRICT_FROZEN

    selection: Literal["absent", "selected"]
    bucket_id: BucketId | None = None
    transition_revision: int = Field(ge=0)
    schema_version: Literal[2]

    @model_validator(mode="after")
    def _validate_selection(self) -> BucketPointer:
        if (self.selection == "selected") != (self.bucket_id is not None):
            raise ValueError("pointer selection and bucket id must agree")
        return self

    @classmethod
    def absent(cls, *, transition_revision: int) -> BucketPointer:
        """Construct the explicit absent-selection tombstone."""
        return cls(
            selection="absent",
            bucket_id=None,
            transition_revision=transition_revision,
            schema_version=POINTER_SCHEMA_VERSION,
        )

    @classmethod
    def selected(cls, *, bucket_id: str, transition_revision: int) -> BucketPointer:
        """Construct one selected current-format record."""
        return cls(
            selection="selected",
            bucket_id=bucket_id,
            transition_revision=transition_revision,
            schema_version=POINTER_SCHEMA_VERSION,
        )

    def to_toml(self) -> str:
        """Return the deterministic strict current-format TOML payload."""
        lines = [f'selection = "{self.selection}"']
        if self.bucket_id is not None:
            bucket_id_escaped = self.bucket_id.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'bucket_id = "{bucket_id_escaped}"')
        lines.extend(
            (
                f"transition_revision = {self.transition_revision}",
                f"schema_version = {self.schema_version}",
            )
        )
        return "\n".join(lines) + "\n"

    @classmethod
    def from_toml(cls, text: str) -> BucketPointer:
        """Strictly parse a current-format pointer record."""
        return cls.model_validate(tomllib.loads(text))


__all__ = ["POINTER_SCHEMA_VERSION", "BucketPointer"]
