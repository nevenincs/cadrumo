"""Exact, policy-free representation for profile recovery secrets.

Imported by the supervised key-derivation worker, which starts afresh for
every wrap and unwrap. The typed refusal is therefore imported only when a
secret is actually refused, so the success path never loads the error
hierarchy.
"""

from __future__ import annotations

from ._kdf_codec import KDF_TRANSPORT_ENCODING


def encode_recovery_secret(secret: str) -> bytes:
    """Encode a recovery secret exactly, without password policy or rewriting."""
    try:
        return secret.encode(KDF_TRANSPORT_ENCODING, errors="strict")
    except UnicodeEncodeError:
        from .errors import ProfileCustodyRecoverySecretError

        raise ProfileCustodyRecoverySecretError("profile recovery secret is not strict UTF-8") from None


def decode_recovery_secret(value: bytes) -> str:
    """Decode exact recovery transport bytes or refuse malformed UTF-8."""
    try:
        return value.decode(KDF_TRANSPORT_ENCODING, errors="strict")
    except UnicodeDecodeError:
        from .errors import ProfileCustodyRecoverySecretError

        raise ProfileCustodyRecoverySecretError("profile recovery secret transport is not strict UTF-8") from None


__all__ = ["decode_recovery_secret", "encode_recovery_secret"]
