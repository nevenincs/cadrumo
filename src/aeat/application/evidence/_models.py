"""Pydantic models for evidence bundles."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ...core.errors import AeatError
from ...core.identity import BucketId
from ...domain.buckets._event import BucketEventObjectType
from ...domain.modelos._ids import (
    CalculationRevisionId,
    FilingRecordId,
    WorkUnitId,
)


class EvidenceBundleNotFoundError(AeatError):
    """Raised when an evidence-bundle lookup misses by id."""


class EvidenceBundleVerificationError(AeatError):
    """Raised when bundle verification fails and the caller refuses ``--force-incomplete``."""


class BundleVerificationState(StrEnum):
    """Closed lifecycle states for a bundle's verification status."""

    PENDING = "pending"
    VERIFIED = "verified"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class VerificationCheck(StrEnum):
    """Named integrity checks a bundle's verification pass runs."""

    MANIFEST_DIGEST = "manifest_digest"
    RECORD_DIGESTS = "record_digests"
    BUCKET_BINDING = "bucket_binding"
    WORK_UNIT_BINDING = "work_unit_binding"
    OBJECT_REACHABILITY = "object_reachability"


class EvidenceBundleCheckResult(BaseModel):
    """One check's outcome from a bundle verification pass."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    check: VerificationCheck
    passed: bool
    detail: str = Field(default="", max_length=500)


class EvidenceRecordRef(BaseModel):
    """One referenced record inside an evidence bundle's manifest."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    object_type: BucketEventObjectType
    object_id: str = Field(min_length=1, max_length=128)
    content_sha256: str = Field(min_length=64, max_length=64)
    payload_size_bytes: int = Field(ge=0)


class EvidenceBundle(BaseModel):
    """One persisted evidence bundle.

    The manifest is content-addressed by ``bundle_id`` (SHA-256 of the
    canonical manifest payload). All record references carry their own
    content digest so bundle verification is offline-pure: given a
    bucket-scoped object store, a verifier can recompute digests and
    confirm reachability without contacting AEAT or any remote service.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bundle_id: str = Field(min_length=64, max_length=64)
    manifest_version: int = Field(ge=1)
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = Field(default=None)
    filing_record_id: FilingRecordId | None = Field(default=None)
    records: tuple[EvidenceRecordRef, ...] = Field(default_factory=tuple)
    verification_state: BundleVerificationState = BundleVerificationState.PENDING
    completeness_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime
    notes: str = Field(default="", max_length=2000)

    @field_serializer("created_at", when_used="json")
    def _serialize_dt(self, value: datetime) -> str:
        return value.isoformat()


def derive_bundle_id(
    *,
    bucket_id: str,
    work_unit_id: str,
    manifest_version: int,
    records: tuple[EvidenceRecordRef, ...],
    calculation_revision_id: str | None = None,
    filing_record_id: str | None = None,
) -> str:
    """Compute the content-addressed bundle_id (SHA-256 hex of canonical inputs)."""
    payload_parts: list[str] = [
        f"version={manifest_version}",
        f"bucket={bucket_id}",
        f"work_unit={work_unit_id}",
        f"revision={calculation_revision_id or ''}",
        f"filing={filing_record_id or ''}",
    ]
    for record in records:
        payload_parts.append(
            f"record={record.object_type.value}:{record.object_id}:{record.content_sha256}",
        )
    canonical = "\n".join(payload_parts).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


__all__ = [
    "BundleVerificationState",
    "EvidenceBundle",
    "EvidenceBundleCheckResult",
    "EvidenceBundleNotFoundError",
    "EvidenceBundleVerificationError",
    "EvidenceRecordRef",
    "VerificationCheck",
    "derive_bundle_id",
    "utcnow",
]
