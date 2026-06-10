"""Strict pydantic v2 record for the per-bucket plaintext manifest.

The bucket manifest sits at ``<aeat-root>/buckets/<bucket-id>/manifest.toml``
and carries only non-sensitive metadata: the bucket identifier and label,
creation and unlock timestamps, the Argon2id KDF parameters and salt
(salt is public per Argon2 design), the recovery-enrollment flag, and a
schema version. The manifest never contains the derived key, the wrapped
key, the passphrase, or any byte derivable from them; those artefacts
travel through the separate master-key surface.

The :class:`ManifestKdfParams` nested model carried here is the
manifest-side shape (algorithm tag, parameter version, the four
Argon2id cost parameters, salt). The canonical OWASP-pinned
constructor and the parameter-window validators live alongside it
under ``master_key/_kdf_params.py``; manifest I/O wires the two
together.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_serializer, field_validator

from .....core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.time._utc import validate_utc_aware
from .._kdf_salt import decode_kdf_salt, encode_kdf_salt, require_kdf_salt_length


class ManifestKdfParams(BaseModel):
    """Argon2id parameters and salt as carried in the bucket manifest.

    Strict pydantic v2 record. The canonical OWASP-baseline constructor
    is declared in :mod:`aeat.adapters.persistence.storage.master_key._kdf_params`;
    this manifest-side record holds whatever parameters the bucket was
    enrolled under so a future cost-bump can be non-breaking.
    """

    model_config = _STRICT_FROZEN

    algorithm: str = Field(min_length=1)
    version: int = Field(ge=1)
    memory_cost: int = Field(ge=1)
    time_cost: int = Field(ge=1)
    parallelism: int = Field(ge=1)
    salt: bytes
    output_length: int = Field(ge=16)

    @field_validator("salt")
    @classmethod
    def _check_salt_length(cls, value: bytes) -> bytes:
        return require_kdf_salt_length(value)

    @field_serializer("salt")
    def _serialise_salt(self, value: bytes) -> str:
        return encode_kdf_salt(value)

    @field_validator("salt", mode="before")
    @classmethod
    def _decode_salt(cls, value: object) -> bytes:
        return decode_kdf_salt(value)


class BucketLifecycleStatus(StrEnum):
    """Plaintext lifecycle marker carried on the bucket manifest.

    The encrypted :class:`~aeat.domain.user_profile.UserProfileStatus`
    record is the lifecycle authority, but reading it costs a bucket
    decryption. The manifest mirrors that status as a plaintext marker
    so the manifest scan can exclude a tombstoned profile from every
    live operator surface (``list`` / ``switch`` / name-uniqueness)
    without unlocking the bucket. The :class:`ProfileRepository` is the
    sole writer of both stores and keeps the two in lockstep.

    Values match :class:`UserProfileStatus` so the application-layer
    repository maps the two enums one-to-one.
    """

    ACTIVE = "active"
    TOMBSTONED = "tombstoned"


class BucketKeySchedule(StrEnum):
    """Data-key schedule used by encrypted records in this bucket."""

    BUCKET_DEK_V1 = "bucket-dek-v1"


class BucketManifest(BaseModel):
    """Plaintext manifest for one per-bucket directory.

    The manifest never carries
    sensitive bytes; see :class:`ManifestKdfParams` for the salt contract.
    """

    model_config = _STRICT_FROZEN

    bucket_id: Annotated[str, Field(min_length=1)]
    label: str
    created_at: datetime
    last_unlocked_at: datetime | None
    kdf_params: ManifestKdfParams
    recovery_enrolled: bool
    idle_lock_minutes: int | None = Field(default=None, gt=0)
    key_schedule: BucketKeySchedule = BucketKeySchedule.BUCKET_DEK_V1
    schema_version: int = Field(ge=1)
    status: BucketLifecycleStatus
    """Plaintext mirror of the encrypted record's lifecycle status.

    Required, with no default. A manifest that omits ``status`` is
    rejected at the read boundary (fail-closed) rather than silently
    hydrating as a live profile — a silent default would risk leaking a
    tombstoned bucket back onto the operator surface. The
    :class:`ProfileRepository` sets it explicitly on every write:
    ``ACTIVE`` at creation, ``TOMBSTONED`` in the same write that
    tombstones the encrypted record.
    """

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, value: object) -> BucketLifecycleStatus:
        """Accept the TOML-native string form of the lifecycle marker.

        The strict model rejects a bare ``str`` for the enum field, but
        the on-disk TOML manifest stores ``status`` as a plain string.
        This pre-validator parses that string back into the enum so the
        manifest round-trips while the public constructor still
        type-checks an explicit :class:`BucketLifecycleStatus`.
        """
        if isinstance(value, BucketLifecycleStatus):
            return value
        if isinstance(value, str):
            return BucketLifecycleStatus(value)
        raise ValueError("status must be a BucketLifecycleStatus or its string value")

    @field_validator("key_schedule", mode="before")
    @classmethod
    def _coerce_key_schedule(cls, value: object) -> BucketKeySchedule:
        if isinstance(value, BucketKeySchedule):
            return value
        if isinstance(value, str):
            return BucketKeySchedule(value)
        raise ValueError("key_schedule must be a BucketKeySchedule or its string value")

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @field_validator("last_unlocked_at")
    @classmethod
    def _check_last_unlocked_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return validate_utc_aware(value)


__all__ = ["BucketKeySchedule", "BucketLifecycleStatus", "BucketManifest", "ManifestKdfParams"]
