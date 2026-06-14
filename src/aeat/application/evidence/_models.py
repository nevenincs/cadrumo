"""Pydantic models for operator-facing evidence bundles.

An evidence bundle is a content-addressed manifest that groups related
persisted records (calculation revisions, filing records, and their
attached objects) under a single verifiable identity. The bundle's
``bundle_id`` is a SHA-256 hash of the canonical manifest inputs so it
is stable across re-imports of the same data and globally unique per
bucket + work-unit + manifest-version triple.

Key types:

* :class:`EvidenceBundle` — the persisted manifest record.
* :class:`EvidenceRecordRef` — one record reference inside the manifest.
* :class:`BundleVerificationState` — closed lifecycle states for
  offline bundle verification.
* :func:`derive_bundle_id` — content-addressed id derivation.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_serializer

from ...core import STRICT_FROZEN_CONFIG
from ...core.errors import AeatError
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.identity import BucketId
from ...core.time import now
from ...domain.buckets._event import BucketEventObjectType
from ...domain.modelos._ids import (
    CalculationRevisionId,
    FilingRecordId,
    WorkUnitId,
)
from ._ids import BundleId


class EvidenceBundleNotFoundError(AeatError):
    """Raised when an evidence-bundle lookup misses by id."""


class EvidenceBundleVerificationError(AeatError):
    """Raised when bundle verification fails and the caller refuses ``--force-incomplete``.

    The verification service raises this when one or more
    :class:`VerificationCheck` items fail and the operator has not
    passed an override flag that permits incomplete bundles.
    """


class BundleVerificationState(StrEnum):
    """Closed lifecycle states for a :class:`EvidenceBundle`'s verification status.

    ``PENDING`` is the initial state when a bundle is first written.
    ``VERIFIED`` means all :class:`VerificationCheck` items passed.
    ``INCOMPLETE`` means reachability or digest checks found missing
    records but the operator accepted the partial bundle.
    ``FAILED`` means at least one blocking integrity check failed.
    """

    PENDING = "pending"
    VERIFIED = "verified"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class VerificationCheck(StrEnum):
    """Named integrity checks a bundle's offline verification pass runs.

    Each member identifies one distinct check the verifier executes
    against the bundle manifest and the backing object store:

    * ``MANIFEST_DIGEST`` — recompute ``bundle_id`` and compare.
    * ``RECORD_DIGESTS`` — re-hash each referenced object payload.
    * ``BUCKET_BINDING`` — confirm the bundle's ``bucket_id`` matches
      the repository it was loaded from.
    * ``WORK_UNIT_BINDING`` — confirm the ``work_unit_id`` exists.
    * ``OBJECT_REACHABILITY`` — confirm every referenced object is
      present in the bucket's object store.
    """

    MANIFEST_DIGEST = "manifest_digest"
    RECORD_DIGESTS = "record_digests"
    BUCKET_BINDING = "bucket_binding"
    WORK_UNIT_BINDING = "work_unit_binding"
    OBJECT_REACHABILITY = "object_reachability"


class EvidenceBundleCheckResult(BaseModel):
    """One :class:`VerificationCheck` outcome from a bundle verification pass.

    ``passed`` is ``True`` when the check succeeded. ``detail`` carries
    a human-readable explanation when the check failed or when extra
    diagnostic context is available.
    """

    model_config = STRICT_FROZEN_CONFIG

    check: VerificationCheck
    passed: bool
    detail: str = Field(default="", max_length=500)


class EvidenceRecordRef(BaseModel):
    """One referenced record entry inside an :class:`EvidenceBundle` manifest.

    ``object_type`` names the ``BucketEventObjectType`` of the record;
    ``object_id`` is its stable store key; ``content_sha256`` is the
    SHA-256 hex digest of the record's raw payload bytes;
    ``payload_size_bytes`` is the byte count used for
    completeness-ratio calculation.
    """

    model_config = STRICT_FROZEN_CONFIG

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

    model_config = STRICT_FROZEN_CONFIG

    bundle_id: BundleId
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
    canonical = "\n".join(payload_parts).encode(UTF_8_ENCODING)
    return sha256_hex(canonical)


def utcnow() -> datetime:
    """Return the current UTC timestamp via :func:`aeat.core.time.now`."""
    return now()


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
