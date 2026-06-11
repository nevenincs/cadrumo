"""Strict pydantic v2 record for the sealed-export archive header.

The export archive header is the plaintext frontmatter of every sealed
export bundle produced by ``aeat config export-bucket``. The wrapped DEK
and the recovery wrap travel as separate archive members; the header
itself carries only the bucket identifier, the manifest digest, the
recovery-presence flag, the archive schema version, and the export
timestamp.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.errors import CoreValidationError
from .....core.identity import BucketId
from .....core.time._utc import validate_utc_aware

_SHA256_HEX_LEN = 64
_LOWER_HEX_DIGITS = frozenset("0123456789abcdef")


class ExportArchiveHeader(BaseModel):
    """Plaintext frontmatter for a sealed bucket-export archive."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    manifest_digest: str = Field(min_length=1)
    recovery_wrap_present: bool
    archive_schema_version: int = Field(ge=1)
    created_at: datetime

    @field_validator("manifest_digest")
    @classmethod
    def _check_manifest_digest(cls, value: str) -> str:
        """Reject anything other than a lowercase hex SHA-256 digest."""
        if len(value) != _SHA256_HEX_LEN:
            raise ValueError("manifest_digest must be a 64-char SHA-256 hex string")
        if any(char not in _LOWER_HEX_DIGITS for char in value):
            raise ValueError("manifest_digest must be lowercase hex")
        return value

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: datetime) -> datetime:
        try:
            return validate_utc_aware(value)
        except CoreValidationError as exc:
            raise ValueError(str(exc)) from exc


__all__ = ["ExportArchiveHeader"]
