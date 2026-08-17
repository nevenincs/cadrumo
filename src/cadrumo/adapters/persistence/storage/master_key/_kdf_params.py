"""Canonical Argon2id parameter record and the window it validates against.

Strict pydantic v2 model declaring the Argon2id KEK-derivation parameters
the substrate accepts. The :meth:`KdfParams.default` classmethod
materialises the OWASP 2024 Password Storage Cheat Sheet baseline:

- ``algorithm`` = ``"argon2id"``
- ``version`` = ``19`` (Argon2 v1.3)
- ``memory_cost`` = ``19 * 1024`` KiB (19 MiB)
- ``time_cost`` = ``2`` iterations
- ``parallelism`` = ``1`` lane
- ``salt`` = 16 bytes
- ``output_length`` = 32 bytes

Validators reject parameter sets outside the supported window, so no
supplied parameter set can drive the KDF into a weaker regime at unlock.

The window constants live here rather than in a package-level module of
their own. They were separated originally because a second, manifest-side
record declared the same axes and could not import this package without
closing a cycle. Both that record and the on-disk key store it validated
have since been deleted with the shared-master surface, leaving this record
as the window's only reader.

Widening the window is a deliberate edit here; a *cost bump* raises a
store's enrolled parameters within it and stays non-breaking.

This window is a KIBIBYTE, continuously-bounded one, deliberately distinct
from the finite mebibyte grid profile custody enrols under: that grid is a
strictly narrower shape, not a wider one, and every value an already-enrolled
store carries must stay readable here.
"""

from __future__ import annotations

import secrets
from typing import Final, Literal, get_args

from pydantic import BaseModel, Field, field_serializer, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .._kdf_salt import KDF_SALT_BYTES, decode_kdf_salt, encode_kdf_salt, require_kdf_salt_length
from ..errors import StorageValidationError

#: Argon2 version 1.3, the only version this substrate derives under.
Argon2Version = Literal[19]

#: Derived KEK length in bytes, fixed by AES-256-GCM.
KdfOutputLength = Literal[32]

# The two single-valued axes are declared ONCE, as the types above, and their
# runtime values read back out. Writing the annotation and the constant
# separately would put the same number in two places.
ARGON2_VERSION: Final = get_args(Argon2Version)[0]
KDF_OUTPUT_BYTES: Final = get_args(KdfOutputLength)[0]

#: OWASP 2024 Password Storage Cheat Sheet baseline, and the floor.
MIN_MEMORY_COST_KIB: Final = 19 * 1024
MAX_MEMORY_COST_KIB: Final = 1024 * 1024
MIN_TIME_COST: Final = 2
MAX_TIME_COST: Final = 16
MIN_PARALLELISM: Final = 1
MAX_PARALLELISM: Final = 8

_SALT_BYTES = KDF_SALT_BYTES


class KdfParams(BaseModel):
    """OWASP-baseline Argon2id parameters with strict validation.

    The constructor for a new enrolment. It reads the window declared above
    rather than restating one. It once shared that window with an on-disk
    record validating the same axes; that record is deleted, so the window now
    has a single reader and the agreement it enforced is no longer at risk.
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
        return require_kdf_salt_length(value, error_type=StorageValidationError)

    @field_serializer("salt")
    def _serialise_salt(self, value: bytes) -> str:
        return encode_kdf_salt(value)

    @field_validator("salt", mode="before")
    @classmethod
    def _decode_salt(cls, value: object) -> bytes:
        return decode_kdf_salt(value, error_type=StorageValidationError)

    @classmethod
    def default(cls) -> KdfParams:
        """Return a :class:`KdfParams` instance with the canonical OWASP 2024 Argon2id baseline parameters."""
        return cls(
            algorithm="argon2id",
            version=ARGON2_VERSION,
            memory_cost=MIN_MEMORY_COST_KIB,
            time_cost=MIN_TIME_COST,
            parallelism=MIN_PARALLELISM,
            salt=secrets.token_bytes(_SALT_BYTES),
            output_length=KDF_OUTPUT_BYTES,
        )


__all__ = [
    "ARGON2_VERSION",
    "KDF_OUTPUT_BYTES",
    "MAX_MEMORY_COST_KIB",
    "MAX_PARALLELISM",
    "MAX_TIME_COST",
    "MIN_MEMORY_COST_KIB",
    "MIN_PARALLELISM",
    "MIN_TIME_COST",
    "Argon2Version",
    "KdfOutputLength",
    "KdfParams",
]
