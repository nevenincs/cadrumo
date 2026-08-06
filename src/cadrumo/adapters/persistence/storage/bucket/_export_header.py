"""Strict pydantic v2 record for the sealed-export archive header.

The export archive header is the plaintext frontmatter of every sealed
export bundle produced by ``aeat config profile archive export``. The wrapped DEK
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
from .....core.identity import BucketId, ContentDigest
from .....core.product_identity import PRODUCT_IDENTITY
from .....core.time import validate_utc_aware


class ExportArchiveHeader(BaseModel):
    """Plaintext frontmatter for a sealed bucket-export archive.

    ``manifest_digest`` is the canonical
    :data:`~core.identity.ContentDigest` of the archive manifest. It
    previously carried a locally-restated lowercase-hex-64 rule, which agreed
    with the canonical alias on every malformed value but disagreed on a valid
    one: the alias strips surrounding whitespace, so a digest that arrived
    padded -- as it can from a text transport -- normalized everywhere else in
    the codebase and was refused here alone. The header sits beside
    ``bucket_id``, already typed through the same identity module, so routing
    the digest through it keeps one rule rather than two that happen to match.
    """

    model_config = _STRICT_FROZEN

    product: str = Field(min_length=1)
    bucket_id: BucketId
    manifest_digest: ContentDigest
    recovery_wrap_present: bool
    archive_schema_version: int = Field(ge=1)
    created_at: datetime

    @field_validator("product")
    @classmethod
    def _check_product(cls, value: str) -> str:
        """Require the canonical product marker with no former-format alias."""
        if value != PRODUCT_IDENTITY.python_package:
            raise ValueError(f"product must be {PRODUCT_IDENTITY.python_package!r}")
        return value

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: datetime) -> datetime:
        try:
            return validate_utc_aware(value)
        except CoreValidationError as exc:
            raise ValueError(str(exc)) from exc


__all__ = ["ExportArchiveHeader"]
