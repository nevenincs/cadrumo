"""Strict pydantic v2 record for the per-bucket plaintext manifest.

The bucket manifest sits at ``<cadrumo-root>/buckets/<bucket-id>/manifest.toml``
and carries only non-sensitive metadata: the bucket identifier and label,
creation and unlock timestamps, the Argon2id KDF parameters and salt
(salt is public per Argon2 design), the recovery-enrollment flag, and a
schema version. The manifest never contains the derived key, the wrapped
key, the passphrase, or any byte derivable from them; those artefacts
travel through the separate master-key surface.

The :class:`ManifestKdfParams` nested model carried here is the
manifest-side shape (algorithm tag, parameter version, the four
Argon2id cost parameters, salt). The canonical OWASP-pinned
constructor lives under ``master_key/_kdf_params.py``; the parameter
window BOTH records validate against lives in ``_kdf_bounds.py``, in
the package they share, because this package cannot import the
master-key package without closing an import cycle -- which is how the
window came to be written twice, with different numbers.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.identity import BucketId
from .....core.time import validate_utc_aware
from .....domain.user_profile import UserProfileStatus
from .._kdf_bounds import (
    MAX_MEMORY_COST_KIB,
    MAX_PARALLELISM,
    MAX_TIME_COST,
    MIN_MEMORY_COST_KIB,
    MIN_PARALLELISM,
    MIN_TIME_COST,
    Argon2Version,
    KdfOutputLength,
)
from .._kdf_salt import decode_kdf_salt, encode_kdf_salt, require_kdf_salt_length


class ManifestKdfParams(BaseModel):
    """Argon2id parameters and salt as carried in the bucket manifest.

    Strict pydantic v2 record holding whatever parameters the bucket was
    enrolled under, so a future cost-bump can be non-breaking. "Whatever
    parameters" means anywhere inside the one :mod:`.._kdf_bounds` window --
    the same window the canonical enrollment record
    :class:`~..master_key._kdf_params.KdfParams` accepts, read from the same
    constants rather than restated here.

    It previously declared only ``ge=1`` lower bounds and a free-form
    ``algorithm``, so this record accepted an 8 KiB single-iteration parameter
    set, a non-Argon2id algorithm name, and a 16-byte output that enrollment
    refuses outright -- while the enrollment record's module documented that a
    tampered manifest could not drive the KDF into a weaker regime at unlock.
    Only one of the two could be right about the same numbers.
    """

    model_config = _STRICT_FROZEN

    algorithm: Literal["argon2id"]
    version: Argon2Version
    memory_cost: int = Field(ge=MIN_MEMORY_COST_KIB, le=MAX_MEMORY_COST_KIB)
    time_cost: int = Field(ge=MIN_TIME_COST, le=MAX_TIME_COST)
    parallelism: int = Field(ge=MIN_PARALLELISM, le=MAX_PARALLELISM)
    salt: bytes
    output_length: KdfOutputLength

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


class BucketKeySchedule(StrEnum):
    """Data-key schedule used by encrypted records in this bucket."""

    BUCKET_DEK_V1 = "bucket-dek-v1"


#: Current on-disk schema version of a bucket manifest.
#:
#: Named here rather than restated at the create call site, so the manifest can
#: enroll in the durability machinery alongside the other persisted formats. The
#: value reached 2 when the key schedule became a stored discriminator, and that
#: bump rode an unrelated routing change without announcing itself — the axis has
#: already moved once unobserved, on the field that decides how a bucket's bytes
#: are unlocked.
BUCKET_MANIFEST_SCHEMA_VERSION: Final[int] = 2

#: Oldest bucket-manifest schema version the read path keeps readable.
#:
#: Equal to the current version: the manifest tier carries no upgrade dispatch,
#: so a floor below current would have no mechanism behind it. Raising the
#: version therefore forces an explicit decision in the same change — raise the
#: floor too (dropping older manifests, the pre-release posture), or land a
#: version-aware reader with an old-manifest restorability test.
BUCKET_MANIFEST_DURABILITY_FLOOR: Final[int] = 2


class BucketManifest(BaseModel):
    """Plaintext manifest for one per-bucket directory.

    The manifest never carries
    sensitive bytes; see :class:`ManifestKdfParams` for the salt contract.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    label: str
    created_at: datetime
    last_unlocked_at: datetime | None
    kdf_params: ManifestKdfParams
    recovery_enrolled: bool
    idle_lock_minutes: int | None = Field(default=None, gt=0)
    session_absolute_minutes: int | None = Field(default=None, gt=0)
    key_schedule: BucketKeySchedule = BucketKeySchedule.BUCKET_DEK_V1
    schema_version: int = Field(ge=1)
    status: UserProfileStatus
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
    def _coerce_status(cls, value: object) -> UserProfileStatus:
        """Accept the TOML-native string form of the lifecycle marker.

        The strict model rejects a bare ``str`` for the enum field, but
        the on-disk TOML manifest stores ``status`` as a plain string.
        This pre-validator parses that string back into the enum so the
        manifest round-trips while the public constructor still
        type-checks an explicit :class:`UserProfileStatus`.
        """
        if isinstance(value, UserProfileStatus):
            return value
        if isinstance(value, str):
            return UserProfileStatus(value)
        raise ValueError("status must be a UserProfileStatus or its string value")

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


__all__ = ["BucketKeySchedule", "BucketManifest", "ManifestKdfParams"]
