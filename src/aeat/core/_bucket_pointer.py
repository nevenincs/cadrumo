"""Strict pydantic v2 record for the active-profile pointer file.

The pointer file lives at ``<aeat-root>/active-profile`` and carries the
canonical default for the active-profile precedence chain
(flag > env > pointer). This record is the typed wrapper around the
pointer file's plaintext content: :class:`BucketPointer`. The storage-layer
term ``bucket`` is preserved on the record's ``bucket_id`` field because the
bucket is the encrypted storage slice the operator profile sits on; the file's
operator-visible name is ``active-profile`` to match the verb noun.

The on-disk representation is single-document TOML keyed by
``bucket_id`` and ``schema_version``. An atomic write-then-rename
helper, :func:`write_pointer`, materialises the pointer; the
:func:`resolve_active_bucket_id` resolver consumes it at startup. Invalid
TOML and pydantic validation failures are deliberate hard failures for
``read_pointer``; they are not treated as "no active profile" because that
would silently fall back to root storage.

This module is also distinct from the application-layer manifest scanners:
:class:`~aeat.application.workflow.ProfileBucketPointer` records are derived
from ``buckets/*/manifest.toml`` and prove registered profile metadata. A
``BucketPointer`` only names the intended active bucket; it does not prove the
bucket exists, read a manifest, or validate lifecycle status. The companion
:mod:`aeat.core._bucket_pointer_io` module owns the file boundary, while this
module owns strict validation and deterministic serialisation only.
"""

from __future__ import annotations

import tomllib

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class BucketPointer(BaseModel):
    """Plaintext pointer to the active bucket id.

    The value object carries only ``bucket_id`` and ``schema_version``. It does
    not read settings, open storage, inspect manifests, or resolve precedence;
    those operations belong to :func:`read_pointer`, :func:`write_pointer`, and
    :func:`resolve_active_bucket_id`.

    Attributes:
        bucket_id: Encrypted profile bucket id selected by the pointer.
        schema_version: Pointer document schema version. Values start at ``1``.
    """

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1)
    schema_version: int = Field(ge=1)

    def to_toml(self) -> str:
        """Serialise the pointer to its single-document TOML representation.

        Emits a deterministic two-line document keyed by ``bucket_id`` and
        ``schema_version``. The output ends with a trailing newline so the
        atomic write-then-rename helper produces a POSIX-clean file. The inverse
        parser is :meth:`from_toml`.
        """
        # Hand-formatted to keep the dependency footprint minimal and the
        # output deterministic; the format is fixed at two scalar keys.
        bucket_id_escaped = self.bucket_id.replace("\\", "\\\\").replace('"', '\\"')
        return f'bucket_id = "{bucket_id_escaped}"\nschema_version = {self.schema_version}\n'

    @classmethod
    def from_toml(cls, text: str) -> BucketPointer:
        """Parse the single-document TOML representation back into a record.

        The parser accepts the exact schema emitted by :meth:`to_toml` and then
        delegates to pydantic validation, so unknown keys, blank bucket ids, and
        invalid schema versions fail before pointer IO can accept the file.

        Args:
            text: Raw TOML string to parse, expected to carry
                ``bucket_id`` and ``schema_version`` scalar keys.

        Returns:
            A validated :class:`BucketPointer` instance.

        Raises:
            tomllib.TOMLDecodeError: If ``text`` is not valid TOML.
            pydantic.ValidationError: If the TOML payload violates the strict
                pointer schema.
        """
        payload = tomllib.loads(text)
        return cls.model_validate(payload)


__all__ = ["BucketPointer"]
