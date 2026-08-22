"""Exact, policy-free representation for profile recovery secrets."""

from __future__ import annotations

from .....core.external_constants import UTF_8_ENCODING
from ._errors import ProfileCustodyRecordError


def encode_recovery_secret(secret: str) -> bytes:
    """Encode a recovery secret exactly, without password policy or rewriting."""
    try:
        return secret.encode(UTF_8_ENCODING, errors="strict")
    except UnicodeEncodeError:
        raise ProfileCustodyRecordError("profile recovery secret is not strict UTF-8") from None


def decode_recovery_secret(value: bytes) -> str:
    """Decode exact recovery transport bytes or refuse malformed UTF-8."""
    try:
        return value.decode(UTF_8_ENCODING, errors="strict")
    except UnicodeDecodeError:
        raise ProfileCustodyRecordError("profile recovery secret transport is not strict UTF-8") from None


__all__ = ["decode_recovery_secret", "encode_recovery_secret"]
