"""Shared salt codec helpers for storage KDF parameter records."""

from __future__ import annotations

import base64

KDF_SALT_BYTES = 16


def require_kdf_salt_length(value: bytes, *, error_type: type[Exception] = ValueError) -> bytes:
    """Return ``value`` when it has the storage KDF salt length."""
    if len(value) != KDF_SALT_BYTES:
        raise error_type(f"salt must be exactly {KDF_SALT_BYTES} bytes")
    return value


def encode_kdf_salt(value: bytes) -> str:
    """Encode KDF salt bytes for JSON/TOML serialization."""
    return base64.b64encode(value).decode("ascii")


def decode_kdf_salt(value: object, *, error_type: type[Exception] = ValueError) -> bytes:
    """Decode a KDF salt from bytes or its base64 string representation."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return base64.b64decode(value.encode("ascii"), validate=True)
    raise error_type("salt must be bytes or base64 string")
