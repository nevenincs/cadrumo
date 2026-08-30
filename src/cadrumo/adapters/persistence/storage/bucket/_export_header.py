"""Strict pydantic v2 record for the sealed-export archive header.

The export archive header is the plaintext frontmatter of every sealed
export bundle. It carries only the product marker, the bucket
identifier, the manifest digest, the archive schema version, and the
export timestamp; the encrypted payload travels as the archive's one
other member.

Recovery material is not part of this transport. A profile's recovery
record is an exclusive per-profile artifact with its own file, schema
and export grammar, so no archive member, header flag, or member-count
rule depends on it. Optional material that could not be produced, or
arrived damaged, can therefore no longer make an otherwise complete
backup read as malformed.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.errors.hierarchy import CoreValidationError
from .....core.identity import BucketId, ContentDigest
from .....core.product_identity import PRODUCT_IDENTITY
from .....core.time import validate_utc_aware

#: The one archive framing this build reads and writes. The header declares
#: it and the model refuses every other value, so a bundle carrying a
#: superseded framing is rejected at the boundary rather than parsed under
#: assumptions its bytes do not satisfy. There is deliberately no branch that
#: accepts a lower version: this is a forward marker, not a compatibility axis.
ARCHIVE_SCHEMA_VERSION = 4


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
    archive_schema_version: int = Field(ge=1)
    created_at: datetime

    @field_validator("product")
    @classmethod
    def _check_product(cls, value: str) -> str:
        """Require the canonical product marker with no former-format alias."""
        if value != PRODUCT_IDENTITY.python_package:
            raise ValueError(f"product must be {PRODUCT_IDENTITY.python_package!r}")
        return value

    @field_validator("archive_schema_version")
    @classmethod
    def _check_archive_schema_version(cls, value: int) -> int:
        """Require the one framing this build understands, in either direction.

        A lower version names a superseded framing whose members and header
        fields differ from these; a higher one names a framing that has not
        been written yet. Reading either would mean interpreting bytes under
        the wrong contract, so both are refused here rather than handled by a
        branch further in.
        """
        if value != ARCHIVE_SCHEMA_VERSION:
            raise ValueError(
                f"archive_schema_version must be {ARCHIVE_SCHEMA_VERSION}, got {value}; "
                f"this build neither reads nor writes any other archive framing",
            )
        return value

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: datetime) -> datetime:
        try:
            return validate_utc_aware(value)
        except CoreValidationError as exc:
            raise ValueError(str(exc)) from exc


__all__ = ["ARCHIVE_SCHEMA_VERSION", "ExportArchiveHeader"]
