"""Strict pydantic v2 record for the active-profile pointer file.

The pointer file lives at ``<aeat-root>/active-profile`` and carries the
canonical default for the active-profile precedence chain
(flag > env > pointer). This record is the typed wrapper around the
pointer file's plaintext content. The storage-layer term ``bucket`` is
preserved on the record's `bucket_id` field because the bucket is the
encrypted storage slice the operator profile sits on; the file's
operator-visible name is `active-profile` to match the verb noun.

The on-disk representation is single-document TOML keyed by
``bucket_id`` and ``schema_version``. An atomic write-then-rename
helper materialises the pointer; a resolver consumes it at startup.
"""

from __future__ import annotations

import tomllib

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class BucketPointer(BaseModel):
    """Plaintext pointer to the active bucket id."""

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1)
    schema_version: int = Field(ge=1)

    def to_toml(self) -> str:
        """Serialise the pointer to its single-document TOML representation.

        Emits a deterministic two-line document keyed by ``bucket_id`` and
        ``schema_version``. The output ends with a trailing newline so the
        atomic write-then-rename helper produces a POSIX-clean file.
        """
        # Hand-formatted to keep the dependency footprint minimal and the
        # output deterministic; the format is fixed at two scalar keys.
        bucket_id_escaped = self.bucket_id.replace("\\", "\\\\").replace('"', '\\"')
        return f'bucket_id = "{bucket_id_escaped}"\nschema_version = {self.schema_version}\n'

    @classmethod
    def from_toml(cls, text: str) -> BucketPointer:
        """Parse the single-document TOML representation back into a record.

        Args:
            text: Raw TOML string to parse, expected to carry
                ``bucket_id`` and ``schema_version`` scalar keys.

        Returns:
            A validated :class:`BucketPointer` instance.
        """
        payload = tomllib.loads(text)
        return cls.model_validate(payload)


__all__ = ["BucketPointer"]
