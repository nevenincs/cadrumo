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

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...adapters.persistence.storage.bucket import ManifestKdfParams
from ...core.identity import ProfileId as _ProfileId
from ...core.time._utc import validate_utc_aware
from ...domain.user_profile import UserProfileRecord, UserProfileStatus
from ...domain.user_profile._errors import UserProfileValidationError

_PROFILE_AGGREGATE_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

_AGGREGATE_MISMATCH_MESSAGE = "profile aggregate projections are inconsistent"


def _aggregate_mismatch_error(*, mismatch: str, translated_message: str) -> UserProfileValidationError:
    return UserProfileValidationError(
        _AGGREGATE_MISMATCH_MESSAGE,
        translated_message=translated_message,
        context={"mismatch": mismatch},
    )


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

    model_config = _PROFILE_AGGREGATE_CONFIG

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
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _validate_cross_store_agreement(self) -> ProfileAggregate:
        """Reject an aggregate whose projections disagree on identity.

        The aggregate is the single object a repository assembles from
        several physical stores; if those stores disagree on the
        profile UUID, the operator-facing label, or the lifecycle
        status the aggregate is already inconsistent and must never be
        constructed. This validator is the last line —
        :func:`verify_profile_integrity` surfaces the same drift with
        operator-facing diagnostics before the aggregate is built.

        ``label`` is carried in two physical stores — the plaintext
        manifest-derived projection and the encrypted record's
        ``display_name``. A rename writes both sequentially; a crash
        between the two writes leaves a torn rename that is otherwise
        undetectable at load. The label agreement check below is the
        structural defence against that torn-rename state.
        """
        if self.record.profile_id != self.profile_id:
            raise _aggregate_mismatch_error(
                mismatch="profile_id",
                translated_message="application.user_profile.errors.aggregate_profile_id_mismatch",
            )
        if self.label != self.record.display_name:
            raise _aggregate_mismatch_error(
                mismatch="label",
                translated_message="application.user_profile.errors.aggregate_label_mismatch",
            )
        if self.record.status is not self.status:
            raise _aggregate_mismatch_error(
                mismatch="status",
                translated_message="application.user_profile.errors.aggregate_status_mismatch",
            )
        return self


__all__ = ["ProfileAggregate"]
