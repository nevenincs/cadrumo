"""The whole-profile in-memory aggregate.

A logical profile is not one record. It is, concretely, a bucket
directory on disk, a plaintext ``manifest.toml``, an encrypted
:class:`UserProfileRecord` row in a per-bucket SQLite table, an
append-only bucket-event history, and the ``active-profile`` pointer.
Historically no object owned that set; every operation wrote whichever
stores it remembered and consistency was by convention.

:class:`ProfileAggregate` is the single in-memory object that holds a
profile's whole state: its immutable UUID identity, its mutable
operator-facing label, the manifest-derived metadata, the secure
:class:`UserProfileRecord`, and its lifecycle status. Application code
loads and saves the aggregate; :class:`ProfileRepository` is the sole
writer of the physical stores it projects onto.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...adapters.persistence.storage.bucket._manifest import ManifestKdfParams
from ...domain.user_profile import UserProfileRecord, UserProfileStatus
from ...domain.user_profile._errors import UserProfileValidationError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_ProfileId = Annotated[str, Field(min_length=1, max_length=96)]


def _ensure_utc(value: datetime) -> datetime:
    """Reject naive datetimes and datetimes whose offset is not UTC."""

    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("datetime must be in UTC")
    return value


class ProfileAggregate(BaseModel):
    """The whole logical profile as one strict, frozen in-memory object.

    The aggregate carries every store the logical profile fragments
    across:

    - ``profile_id`` — the immutable UUIDv4 identity. The bucket
      directory, the secure-object key, and the active-profile pointer
      all key on it.
    - ``label`` — the operator-chosen display name. Mutable; carried
      both in the manifest and the secure record.
    - ``manifest`` fields (``created_at``, ``kdf_params``,
      ``recovery_enrolled``, ``manifest_schema_version``) — the
      plaintext bucket-metadata projection.
    - ``record`` — the encrypted :class:`UserProfileRecord`.
    - ``status`` — the lifecycle status, mirrored from the record so
      consumers can read it without unwrapping ``record``.
    """

    model_config = _STRICT_FROZEN

    profile_id: _ProfileId
    label: str = Field(min_length=1, max_length=160)
    created_at: datetime
    kdf_params: ManifestKdfParams
    recovery_enrolled: bool
    manifest_schema_version: int = Field(ge=1)
    record: UserProfileRecord
    status: UserProfileStatus

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value)

    @model_validator(mode="after")
    def _validate_cross_store_agreement(self) -> ProfileAggregate:
        """Reject an aggregate whose projections disagree on identity.

        The aggregate is the single object a repository assembles from
        several physical stores; if those stores disagree on the
        profile UUID or the lifecycle status the aggregate is already
        inconsistent and must never be constructed. This validator is
        the last line — :func:`verify_profile_integrity` surfaces the
        same drift with operator-facing diagnostics before the
        aggregate is built.
        """

        if self.record.profile_id != self.profile_id:
            raise UserProfileValidationError(
                f"aggregate profile_id {self.profile_id!r} disagrees with "
                f"record.profile_id {self.record.profile_id!r}"
            )
        if self.record.status is not self.status:
            raise UserProfileValidationError(
                f"aggregate status {self.status} disagrees with "
                f"record.status {self.record.status}"
            )
        return self


__all__ = ["ProfileAggregate"]
