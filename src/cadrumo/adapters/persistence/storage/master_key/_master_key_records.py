"""Persisted document records for master-key storage."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .._kdf_salt import decode_kdf_salt, require_kdf_salt_length
from ..errors import StorageValidationError
from ._kdf_params import (
    _MAX_MEMORY_COST_KIB,
    _MAX_PARALLELISM,
    _MAX_TIME_COST,
    _MIN_MEMORY_COST_KIB,
    _MIN_PARALLELISM,
    _MIN_TIME_COST,
)
from ._master_key_derivation import KDF_PARAMS_VERSION


class _EnvelopeFact(BaseModel):
    """A single fact entry within an :class:`EnvelopeDocument` payload."""

    model_config = ConfigDict(extra="allow")

    path: str
    value: object = None


class _EnvelopePayload(BaseModel):
    """The ``payload`` dict inside an :class:`EnvelopeDocument`."""

    model_config = ConfigDict(extra="allow")

    facts: list[_EnvelopeFact] = Field(default_factory=list)


class EnvelopeDocument(BaseModel):
    """Typed representation of a decrypted user-profile envelope JSON document."""

    model_config = ConfigDict(extra="allow")

    payload: _EnvelopePayload | None = None


class _KdfParameters(BaseModel):
    """On-disk record of the Argon2id parameters used to derive the KEK.

    The Argon2 cost fields carry the same OWASP-baseline validation window as the
    bucket-manifest :class:`KdfParams`, so a tampered or buggy ``master.kdf`` that
    declares a below-floor cost is refused on read instead of silently deriving a
    weakened KEK.

    ``salt_b64`` carries that same treatment on the salt, through the one
    :mod:`.._kdf_salt` contract every storage KDF record shares. It previously
    accepted anything that decoded, and the reader handed the result straight to
    Argon2: an 8-byte salt derived a different KEK and surfaced as a *passphrase
    mismatch*, sending the operator to recover a passphrase that was never
    wrong, while a 1-byte salt reached the library and leaked a raw
    ``argon2.exceptions.HashingError``.
    """

    model_config = _STRICT_FROZEN

    version: int = Field(default=KDF_PARAMS_VERSION)
    algorithm: Literal["argon2id"] = Field(default="argon2id")
    memory_cost: int = Field(ge=_MIN_MEMORY_COST_KIB, le=_MAX_MEMORY_COST_KIB)
    time_cost: int = Field(ge=_MIN_TIME_COST, le=_MAX_TIME_COST)
    parallelism: int = Field(ge=_MIN_PARALLELISM, le=_MAX_PARALLELISM)
    salt_b64: str

    @field_validator("salt_b64")
    @classmethod
    def _check_salt_b64(cls, value: str) -> str:
        """Refuse a salt that is not canonical base64 of exactly the KDF length."""
        require_kdf_salt_length(
            decode_kdf_salt(value, error_type=StorageValidationError),
            error_type=StorageValidationError,
        )
        return value

    @property
    def salt(self) -> bytes:
        """Return the decoded salt.

        Exactly :data:`~.._kdf_salt.KDF_SALT_BYTES` bytes: the field validator
        already refused every other length, so no caller re-decodes or
        re-checks. Owning the codec here is what keeps the length rule and the
        bytes the derivation actually consumes from being two separate
        decisions.
        """
        decoded = decode_kdf_salt(self.salt_b64, error_type=StorageValidationError)
        return require_kdf_salt_length(decoded, error_type=StorageValidationError)


class _KdfVersionEnvelope(BaseModel):
    """Minimal version-gate model for the master.kdf preflight check."""

    model_config = ConfigDict(extra="allow")

    version: int | str | None = None


#: Current on-disk schema version of a wrapped bucket-DEK document.
#:
#: Declared as a named constant so the wrapped-DEK format can enroll in the
#: durability machinery alongside the secure-object, bundle and archive tiers.
#: The document model below pins the same number as a ``Literal``, which is
#: what actually refuses a foreign version at read; the tier lineage gate
#: asserts the two agree, so this constant cannot drift away from the
#: constraint it describes.
BUCKET_DEK_SCHEMA_VERSION: Final[int] = 1

#: Oldest wrapped bucket-DEK schema version the read path keeps readable.
#:
#: Equal to the current version: the ``Literal`` accepts exactly one value, so
#: the readable range is a single point and there is no upgrade dispatch behind
#: it. Raising the current version without deciding what happens to documents
#: below it would strand the wrapped key that unlocks every byte in a bucket,
#: which is why the lineage gate pins this equality rather than leaving it
#: implied.
BUCKET_DEK_DURABILITY_FLOOR: Final[int] = 1


class _WrappedBucketDekDocument(BaseModel):
    """On-disk JSON envelope for one bucket's wrapped DEK."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1] = 1
    nonce_b64: str
    ciphertext_b64: str
    tag_b64: str
