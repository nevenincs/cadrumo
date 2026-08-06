"""Argon2id derivation constants and helpers for file-backed master keys."""

from __future__ import annotations

from typing import Final

from argon2.exceptions import Argon2Error
from argon2.low_level import Type as _Argon2Type
from argon2.low_level import hash_secret_raw as _argon2_hash_secret_raw

from .._kdf_salt import KDF_SALT_BYTES
from ..crypto import KEY_SIZE
from ..errors import StorageValidationError

ARGON2_MEMORY_COST_KIB: Final[int] = 19 * 1024
"""Argon2id ``memory_cost`` in KiB (19 MiB — OWASP-current top tier)."""

ARGON2_TIME_COST: Final[int] = 2
"""Argon2id ``time_cost`` (number of iterations) — OWASP-current top tier."""

ARGON2_PARALLELISM: Final[int] = 1
"""Argon2id ``parallelism`` — OWASP-current top tier."""

SALT_SIZE: Final[int] = KDF_SALT_BYTES
"""Per-store salt size in bytes.

Read from the shared storage KDF salt contract rather than restated, so the
length a store is MINTED with cannot drift from the length its record is
VALIDATED against.
"""

KDF_PARAMS_VERSION: Final[int] = 2
"""On-disk KDF parameter shape accepted by the file-backed provider."""


def derive_kek(passphrase: bytes, salt: bytes) -> bytes:
    """Derive a 32-byte KEK from the operator's passphrase and per-store salt."""
    return derive_kek_with_params(
        passphrase,
        salt,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    )


def derive_kek_with_params(
    passphrase: bytes,
    salt: bytes,
    *,
    memory_cost: int,
    time_cost: int,
    parallelism: int,
) -> bytes:
    """Derive a 32-byte KEK with explicit persisted Argon2id parameters.

    Raises:
        StorageValidationError: When the library refuses the supplied material.
            The callers' records validate their parameters before reaching
            here, so this is the backstop for whatever those records do not
            constrain -- it exists because the alternative is an
            ``argon2.exceptions`` type escaping the storage boundary into a CLI
            that cannot render it.
    """
    try:
        return _argon2_hash_secret_raw(
            secret=passphrase,
            salt=salt,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=KEY_SIZE,
            type=_Argon2Type.ID,
        )
    except Argon2Error as exc:
        raise StorageValidationError(f"Argon2id refused the supplied KDF material: {exc}") from exc
