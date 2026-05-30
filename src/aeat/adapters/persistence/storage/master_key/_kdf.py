"""Argon2id KEK derivation for the per-bucket unlock pipeline.

The substrate derives every passphrase-bound key-encryption key via
Argon2id at the OWASP 2024 baseline parameters declared by
`KdfParams.default()`. The on-disk manifest carries
the parameter set the bucket was enrolled under so a future cost-bump is
non-breaking; this helper consumes whatever `ManifestKdfParams` the
manifest supplies and routes it through the existing `argon2-cffi`
dependency.

The helper is a thin typed wrapper. It does not maintain caches or
module-global state; the unlock pipeline owns the resulting bytes
through a `BucketSession`.
"""

from __future__ import annotations

from argon2.low_level import Type, hash_secret_raw

from ..bucket._manifest import ManifestKdfParams
from ..errors import KeyDerivationError

_OUTPUT_BYTES = 32


def derive_kek(passphrase: bytes, kdf_params: ManifestKdfParams) -> bytes:
    """Derive a 32-byte KEK from `passphrase` and the manifest's `kdf_params`.

    Args:
        passphrase: Operator passphrase encoded UTF-8.
        kdf_params: Manifest-side KDF record carrying algorithm,
            parameter version, the Argon2id cost parameters, the salt,
            and the requested output length.

    Returns:
        Exactly 32 bytes of Argon2id output suitable for AES-256-GCM
        wrapping of the bucket's data-encryption key.

    Raises:
        KeyDerivationError: If `kdf_params.algorithm` is not `argon2id` or
            `kdf_params.output_length` is not 32.
    """

    if kdf_params.algorithm != "argon2id":
        raise KeyDerivationError(
            f"unsupported KDF algorithm {kdf_params.algorithm!r}; expected 'argon2id'",
        )
    if kdf_params.output_length != _OUTPUT_BYTES:
        raise KeyDerivationError(
            f"unsupported KDF output_length {kdf_params.output_length}; expected {_OUTPUT_BYTES}",
        )

    return hash_secret_raw(
        secret=passphrase,
        salt=kdf_params.salt,
        time_cost=kdf_params.time_cost,
        memory_cost=kdf_params.memory_cost,
        parallelism=kdf_params.parallelism,
        hash_len=kdf_params.output_length,
        type=Type.ID,
    )


__all__ = ["derive_kek"]
