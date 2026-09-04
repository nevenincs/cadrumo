"""Argon2id derivation with explicit, caller-supplied parameters.

The cost constants and the no-parameter convenience wrapper that used them are
deleted with the file-backed master-key provider they belonged to. Every
surviving caller states its own Argon2id parameters, because those parameters
are persisted beside the material they protect and must be read back from it
rather than re-derived from a module constant that may since have moved.
"""

from __future__ import annotations

from argon2.exceptions import Argon2Error
from argon2.low_level import Type as _Argon2Type
from argon2.low_level import hash_secret_raw as _argon2_hash_secret_raw

from ..crypto.aead import KEY_SIZE
from ..errors import StorageValidationError


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
