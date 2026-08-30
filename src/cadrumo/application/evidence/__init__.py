"""Public facade for :class:`EvidenceBundle` audit services.

The evidence bundle is a bucket-scoped, work-unit-bound
:class:`EvidenceBundle` manifest plus :class:`EvidenceRecordRef` records
used to package the provenance of a modelo calculation, verification, or
filing for offline inspection and audit handoff. Bundles are durable
artifacts stored inside the active bucket; they are not the source of
relational truth.

Bundle manifests can reference :class:`~WorkUnit`,
:class:`~CalculationRevision`, and
:class:`~ModeloRecord` payloads by stable id, with each
record typed by :class:`domain.buckets.BucketEventObjectType`. They are
audit packaging records, not purchase-invoice evidence or official AEAT filing
evidence claims.

The persisted manifest is encrypted bucket-local state managed by
:class:`EvidenceBundleRepository`. The ZIP produced by ``export`` is an
operator-directed plaintext handoff artifact written only to the caller's
requested path after verification.

Verbs supported by the operator surface (`aeat app modelo audit ...`):
    show     - render the bundle's manifest and referenced records
    check    - re-verify the bundle's integrity (report-only)
    export   - write a ZIP archive with the manifest emitted last

Bucket events emitted by mutating operations:
    modelo.audit.verified  - a fresh verify-pass completed
    modelo.audit.exported  - a ZIP was successfully written

The audit surface never contacts AEAT and never performs live submission.
Export refuses on failed verification unless ``--force-incomplete`` is
explicitly passed at the operator boundary.

See Also:
    :class:`EvidenceBundleService`
        Build, verify, and export service for audit bundles.
    :class:`EvidenceBundleRepository`
        Encrypted bucket-local repository for bundle manifests.
    :class:`EvidenceBundleVerificationReport`
        Integrity-check summary emitted by ``check`` and ``export`` flows.
    :class:`BundleVerificationState`
        Closed verification state vocabulary for bundle manifests.
    :class:`application.ledger.evidence.PurchaseInvoiceEvidence`
        Source-document evidence for ledger rows.
    :class:`~ExternalEvidence`
        Official filing evidence stamped on current modelo filing records.
"""

from __future__ import annotations

from ._models import (
    BundleVerificationState,
    EvidenceBundle,
    EvidenceBundleCheckResult,
    EvidenceBundleNotFoundError,
    EvidenceBundleVerificationError,
    EvidenceRecordRef,
    VerificationCheck,
    derive_bundle_id,
)
from ._profile_legal_hold import LegalHoldCaseAuthority, try_record_legal_hold_snapshot
from ._service import (
    EvidenceBundleRepository,
    EvidenceBundleService,
    EvidenceBundleVerificationReport,
)

__all__ = [
    "BundleVerificationState",
    "EvidenceBundle",
    "EvidenceBundleCheckResult",
    "EvidenceBundleNotFoundError",
    "EvidenceBundleRepository",
    "EvidenceBundleService",
    "EvidenceBundleVerificationError",
    "EvidenceBundleVerificationReport",
    "EvidenceRecordRef",
    "LegalHoldCaseAuthority",
    "VerificationCheck",
    "derive_bundle_id",
    "try_record_legal_hold_snapshot",
]
