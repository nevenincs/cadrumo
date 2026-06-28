"""Strict pydantic v2 record for the BIP-39 recovery wrap envelope.

Carries the wrapped DEK, AES-GCM nonce, AES-GCM tag, the 24-word
recovery-code word count, the HKDF info string, and the creation
timestamp. The mnemonic itself is never stored; only the wrap derived
from the mnemonic-bound KEK travels in this envelope.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.time._utc import validate_utc_aware
from ..errors import StorageValidationError


def _decode_b64(value: str) -> bytes:
    """Decode a strict base64 string; raise if malformed."""
    return base64.b64decode(value.encode("ascii"), validate=True)


def _validate_b64(value: str) -> str:
    """Accept a base64 string and verify it decodes; return canonical form."""
    decoded = _decode_b64(value)
    re_encoded = base64.b64encode(decoded).decode("ascii")
    if re_encoded != value:
        raise StorageValidationError("base64 field is not in canonical form")
    return value


class RecoveryRecord(BaseModel):
    """BIP-39 recovery envelope wrapping one bucket's DEK."""

    model_config = _STRICT_FROZEN

    wrapped_dek_b64: str = Field(min_length=1)
    nonce_b64: str = Field(min_length=1)
    tag_b64: str = Field(min_length=1)
    mnemonic_word_count: Literal[24]
    hkdf_info: str = Field(min_length=1)
    created_at: datetime

    @field_validator("wrapped_dek_b64", "nonce_b64", "tag_b64")
    @classmethod
    def _check_b64(cls, value: str) -> str:
        return _validate_b64(value)

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)


__all__ = ["RecoveryRecord"]
