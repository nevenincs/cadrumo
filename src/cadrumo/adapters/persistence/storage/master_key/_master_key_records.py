"""Persisted document records for master-key storage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
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
    """

    model_config = _STRICT_FROZEN

    version: int = Field(default=KDF_PARAMS_VERSION)
    algorithm: Literal["argon2id"] = Field(default="argon2id")
    memory_cost: int = Field(ge=_MIN_MEMORY_COST_KIB, le=_MAX_MEMORY_COST_KIB)
    time_cost: int = Field(ge=_MIN_TIME_COST, le=_MAX_TIME_COST)
    parallelism: int = Field(ge=_MIN_PARALLELISM, le=_MAX_PARALLELISM)
    salt_b64: str


class _KdfVersionEnvelope(BaseModel):
    """Minimal version-gate model for the master.kdf preflight check."""

    model_config = ConfigDict(extra="allow")

    version: int | str | None = None


class _WrappedBucketDekDocument(BaseModel):
    """On-disk JSON envelope for one bucket's wrapped DEK."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1] = 1
    nonce_b64: str
    ciphertext_b64: str
    tag_b64: str
