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

Bundle manifests reference work-unit, calculation-revision, and
filing-record payloads without replacing those catalogues as the source
of truth. Verification replays the manifest against supplied object
bytes and reports reachability and digest results without contacting AEAT.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_serializer

from ...core import STRICT_FROZEN_CONFIG, ElidedProse, Hex64Str
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.identity import BucketId, CalculationRevisionId, ContentDigest, FilingRecordId, WorkUnitId
from ...core.unit_proportion import UnitFraction
from ...domain.buckets.event import BucketEventObjectType
from .bundle_text import EvidenceBundleNotes


class EvidenceBundleNotFoundError(CadrumoError):
    """Raised when an evidence-bundle lookup misses by id."""


class EvidenceBundleVerificationError(CadrumoError):
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


#: The bundle-check ``detail`` annotation: elides rather than refusing.
#:
#: A failed check explains itself by interpolating the object ids it could not
#: reach. Refusing the RESULT over the length of that explanation would lose the
#: verification outcome as well as its reason. Empty is the documented default
#: for a check that passed with nothing to add.
_CheckDetail = Annotated[str, ElidedProse(500, min_length=0)]


class EvidenceBundleCheckResult(BaseModel):
    """One :class:`VerificationCheck` outcome from a bundle verification pass.

    ``passed`` is ``True`` when the check succeeded. ``detail`` carries
    a human-readable explanation when the check failed or when extra
    diagnostic context is available.
    """

    model_config = STRICT_FROZEN_CONFIG

    check: VerificationCheck
    passed: bool
    detail: _CheckDetail = ""


class EvidenceRecordRef(BaseModel):
    """One referenced record entry inside an :class:`EvidenceBundle` manifest.

    ``object_type`` names the :class:`BucketEventObjectType` of the
    record; ``object_id`` is its stable store key; ``content_sha256`` is
    the canonical :data:`~core.identity.ContentDigest` of the record's raw
    payload bytes, so a non-hex digest is refused on construction rather
    than at the later verification pass that recomputes it;
    ``payload_size_bytes`` is the byte count used for
    completeness-ratio calculation.
    """

    model_config = STRICT_FROZEN_CONFIG

    object_type: BucketEventObjectType
    object_id: str = Field(min_length=1, max_length=128)
    content_sha256: ContentDigest
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

    bundle_id: Hex64Str
    manifest_version: int = Field(ge=1)
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = Field(default=None)
    filing_record_id: FilingRecordId | None = Field(default=None)
    records: tuple[EvidenceRecordRef, ...] = Field(default_factory=tuple)
    verification_state: BundleVerificationState = BundleVerificationState.PENDING
    completeness_ratio: UnitFraction = 1.0
    created_at: datetime
    notes: EvidenceBundleNotes = ""

    @field_serializer("created_at", when_used="json")
    def _serialize_dt(self, value: datetime) -> str:
        return value.isoformat()


def derive_bundle_id(
    *,
    bucket_id: str,
    work_unit_id: str,
    manifest_version: int,
    records: tuple[EvidenceRecordRef, ...],
    calculation_revision_id: CalculationRevisionId | None = None,
    filing_record_id: str | None = None,
) -> str:
    """Compute the content-addressed ``bundle_id`` for canonical inputs.

    The digest covers manifest version, bucket id, work-unit id,
    optional calculation revision id, optional filing record id, and the
    ordered :class:`EvidenceRecordRef` object type/id/content-digest
    triples.
    """
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


__all__ = [
    "BundleVerificationState",
    "EvidenceBundle",
    "EvidenceBundleCheckResult",
    "EvidenceBundleNotFoundError",
    "EvidenceBundleVerificationError",
    "EvidenceRecordRef",
    "VerificationCheck",
    "derive_bundle_id",
]
