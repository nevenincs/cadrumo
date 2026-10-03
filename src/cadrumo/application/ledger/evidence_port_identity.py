"""Shared exact-profile identity and revision capability admission for evidence."""

from __future__ import annotations

from ...core.bucket_pointer import require_active_bucket_id
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .evidence_ports import (
    LedgerEvidencePorts,
    ProfileBoundEvidenceAttachmentIngestorProtocol,
    RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol,
)


def require_exact_evidence_ports(
    ports: LedgerEvidencePorts,
    *,
    bucket_id: str,
) -> RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol:
    """Require one bound custody identity and real evidence/event CAS capabilities."""
    evidence_objects = getattr(ports.evidence_repository, "secure_object_repository", None)
    event_objects = getattr(ports.bucket_event_repository, "secure_object_repository", None)
    if (
        evidence_objects is None
        or evidence_objects is not event_objects
        or not isinstance(ports.attachment_ingestor, ProfileBoundEvidenceAttachmentIngestorProtocol)
        or ports.attachment_ingestor.secure_object_repository is not evidence_objects
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if not isinstance(ports.evidence_repository, RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if not callable(getattr(ports.bucket_event_repository, "load_revisioned", None)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if bucket_id != require_active_bucket_id():
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports.evidence_repository
