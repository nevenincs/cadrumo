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

import base64
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_SALT_BYTES = 16


def _ensure_utc(value: datetime) -> datetime:
    """Reject naive datetimes and datetimes whose offset is not UTC."""

    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("datetime must be in UTC")
    return value


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
        if len(value) != _SALT_BYTES:
            raise ValueError(f"salt must be exactly {_SALT_BYTES} bytes")
        return value

    @field_serializer("salt")
    def _serialise_salt(self, value: bytes) -> str:
        return base64.b64encode(value).decode("ascii")

    @field_validator("salt", mode="before")
    @classmethod
    def _decode_salt(cls, value: object) -> bytes:
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return base64.b64decode(value.encode("ascii"), validate=True)
        raise TypeError("salt must be bytes or base64 string")


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
    schema_version: int = Field(ge=1)

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value)

    @field_validator("last_unlocked_at")
    @classmethod
    def _check_last_unlocked_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _ensure_utc(value)


__all__ = ["BucketManifest", "ManifestKdfParams"]
