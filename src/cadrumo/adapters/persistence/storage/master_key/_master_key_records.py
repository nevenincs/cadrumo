"""Persisted document records for master-key storage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .._kdf_salt import decode_kdf_salt, require_kdf_salt_length
from ..errors import StorageValidationError
from ._kdf_params import (
    MAX_MEMORY_COST_KIB,
    MAX_PARALLELISM,
    MAX_TIME_COST,
    MIN_MEMORY_COST_KIB,
    MIN_PARALLELISM,
    MIN_TIME_COST,
)


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
    enrolment record :class:`~._kdf_params.KdfParams` beside it -- read from that
    module rather than restated -- so a tampered or buggy ``master.kdf`` that
    declares a below-floor cost is refused on read instead of silently deriving a
    weakened KEK.

    ``salt_b64`` carries that same treatment on the salt, through the one
    :mod:`.._kdf_salt` contract every storage KDF record shares. It previously
    accepted anything that decoded, and the reader handed the result straight to
    Argon2: an 8-byte salt derived a different KEK and surfaced as a *passphrase
    mismatch*, sending the operator to recover a passphrase that was never
    wrong, while a 1-byte salt reached the library and leaked a raw
    ``argon2.exceptions.HashingError``.

    ``version`` is required and carries no default. It once defaulted to the
    current marker, which made the record silently tolerant: any construction
    omitting it — including a future consumer parsing a document that declares
    no version — acquired the current marker as though the document had claimed
    it. The production read path never reached that default, because the
    version gate refuses an undeclared document first, so the tolerance was
    latent rather than live. Requiring the field keeps it that way by
    construction instead of by the ordering of two modules: every writer states
    the marker it is stamping.
    """

    model_config = _STRICT_FROZEN

    version: int
    algorithm: Literal["argon2id"] = Field(default="argon2id")
    memory_cost: int = Field(ge=MIN_MEMORY_COST_KIB, le=MAX_MEMORY_COST_KIB)
    time_cost: int = Field(ge=MIN_TIME_COST, le=MAX_TIME_COST)
    parallelism: int = Field(ge=MIN_PARALLELISM, le=MAX_PARALLELISM)
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
    """Minimal version-gate model for the master.kdf preflight check.

    ``version`` is required. The model exists solely to establish what format
    the file claims to be BEFORE strict parsing, and while the field defaulted
    to ``None`` a file carrying no version at all satisfied the preview and
    reached the comparison with an absent marker standing in for a real claim
    -- a preflight that could not fail on the one document it exists to catch.

    The annotation stays deliberately loose on TYPE while being strict on
    PRESENCE. A file declaring a non-integer version is a version this build
    does not accept, and routing it through the typed, runbook-pointing version
    error that names the offending value is more useful to an operator than a
    raw validation failure. Absence is the case with nothing to name, so it is
    the case the model itself refuses.
    """

    model_config = ConfigDict(extra="allow")

    version: int | str
