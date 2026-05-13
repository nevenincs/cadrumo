"""Pydantic v2 models for the archive bundle wire format.

The archive bundle is a portable, human-readable, versioned snapshot of
every secure-object the user owns: invoice catalogue, transaction
catalogue, filing drafts, and any other namespace registered against the
:mod:`aeat.application.archive._registry`. Records carry the same
``Envelope`` shape the per-domain repositories already write, so a
restore operation re-saves through those repositories without touching
the storage primitives directly.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.classification import SensitivityClass

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

#: Wire-format version of the archive bundle itself.
ARCHIVE_BUNDLE_SCHEMA_VERSION = 1


class ConflictPolicy(StrEnum):
    """Policy applied when a restored record collides with an existing object.

    Members:
        KEEP: The existing object wins; the bundle entry is skipped.
        OVERWRITE: The bundle entry replaces the existing object.
        FAIL: The first collision aborts the restore with
            :class:`aeat.application.archive.ArchiveConflictError`.
    """

    KEEP = "keep"
    OVERWRITE = "overwrite"
    FAIL = "fail"


class ArchiveRecord(BaseModel):
    """One namespaced object captured in an archive bundle.

    Attributes:
        namespace: The :class:`SecureObjectRepository` namespace
            (e.g. ``"aeat.domain.invoices"``).
        object_key: Natural key for namespaces whose key derives from
            the envelope payload (single-object constants like
            ``"catalogue"`` or per-record fields like ``draft_id``).
            ``None`` when ``hashed_object_key_b64`` is set instead.
        hashed_object_key_b64: Base64-encoded 32-byte HMAC digest for
            namespaces whose natural key is not recoverable from the
            payload (path-keyed namespaces such as
            ``aeat.application.profile.bucket``). The receiving side
            must share the master key the digest was computed under;
            cross-master-key restores cannot use this field.
        classification: The :class:`SensitivityClass` declared by the
            owning repository.
        schema_version: Envelope schema version expected by the
            consumer of this namespace.
        written_at: Timezone-aware datetime captured at the original
            write time. Round-tripped on restore.
        envelope_json: The decoded :class:`Envelope` JSON object,
            including the typed payload. Stored as ``dict`` so the
            bundle is self-describing without a per-namespace pydantic
            type at the bundle layer.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: str | None = None
    hashed_object_key_b64: str | None = None
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    envelope_json: dict[str, Any]

    @field_validator("written_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("written_at must be timezone-aware")
        return value

    @field_validator("hashed_object_key_b64")
    @classmethod
    def _exactly_one_key(cls, value: str | None, info: Any) -> str | None:
        # ``object_key`` and ``hashed_object_key_b64`` are mutually exclusive;
        # pydantic v2's field-level validator runs sequentially so we cross-check
        # against the already-validated ``object_key`` via ``info.data``.
        natural = info.data.get("object_key")
        if natural is not None and value is not None:
            raise ValueError(
                "ArchiveRecord may set either object_key or hashed_object_key_b64, not both",
            )
        if natural is None and value is None:
            raise ValueError(
                "ArchiveRecord must set one of object_key or hashed_object_key_b64",
            )
        return value


class ArchiveBundle(BaseModel):
    """Versioned envelope wrapping every :class:`ArchiveRecord` in one export.

    Attributes:
        bundle_schema_version: Wire-format version of the bundle
            itself; consumers refuse newer-than-supported values.
        bundle_id: Caller-provided identifier (e.g. an ISO datestamp);
            free-form, used only for human auditing.
        created_at: Timezone-aware datetime when the bundle was
            produced.
        records: One entry per (namespace, object_key) pair captured.
    """

    model_config = _STRICT_FROZEN

    bundle_schema_version: int = Field(default=ARCHIVE_BUNDLE_SCHEMA_VERSION, ge=1)
    bundle_id: str = Field(min_length=1)
    created_at: datetime
    records: tuple[ArchiveRecord, ...]

    @field_validator("created_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class RestoreOutcome(StrEnum):
    """Outcome reported per record after a restore operation."""

    WROTE = "wrote"
    SKIPPED_KEEP = "skipped_keep"
    OVERWROTE = "overwrote"


class RestoreEntry(BaseModel):
    """One entry in :class:`RestoreReport.entries`.

    The ``object_key`` field is either the natural key (for payload-
    keyed adapters) or the base64-encoded HMAC digest prefixed with
    ``hashed:`` (for hashed-passthrough adapters).
    """

    model_config = _STRICT_FROZEN

    namespace: str
    object_key: str
    outcome: RestoreOutcome


class RestoreReport(BaseModel):
    """Result of a successful restore operation."""

    model_config = _STRICT_FROZEN

    bundle_id: str
    entries: tuple[RestoreEntry, ...]


__all__ = [
    "ARCHIVE_BUNDLE_SCHEMA_VERSION",
    "ArchiveBundle",
    "ArchiveRecord",
    "ConflictPolicy",
    "RestoreEntry",
    "RestoreOutcome",
    "RestoreReport",
]
