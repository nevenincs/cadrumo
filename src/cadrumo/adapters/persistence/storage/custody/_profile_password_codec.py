"""Exact byte transport for profile passwords, under the canonical policy.

Imported by the supervised key-derivation worker, which starts afresh for
every wrap and unwrap. The typed refusal is therefore imported only when a
password is actually refused, so the success path never loads the error
hierarchy.
"""

from __future__ import annotations

from .....core.credentials import assess_profile_password
from ._kdf_codec import KDF_TRANSPORT_ENCODING


def encode_profile_password(password: str) -> bytes:
    """Encode an exact password after canonical defense-in-depth assessment."""
    assessment = assess_profile_password(password)
    if assessment.reason is not None:
        from .errors import ProfileCustodyPasswordError

        raise ProfileCustodyPasswordError(
            f"profile password refused by canonical policy: {assessment.reason.value}",
        )
    return password.encode(KDF_TRANSPORT_ENCODING, errors="strict")


def decode_profile_password(value: bytes) -> str:
    """Strictly decode and assess a password received through byte transport."""
    try:
        password = value.decode(KDF_TRANSPORT_ENCODING, errors="strict")
    except UnicodeDecodeError as exc:
        from .errors import ProfileCustodyPasswordError

        raise ProfileCustodyPasswordError("profile password transport is not strict UTF-8") from exc
    encode_profile_password(password)
    return password


__all__ = ["decode_profile_password", "encode_profile_password"]
