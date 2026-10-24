"""Concrete evidence catalogue, attachment custody and renderer for the page read."""

from __future__ import annotations

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..adapters.inbound.pdf.page_image import PageImageRenderer
from ..application.ledger.evidence_page_contracts import EvidencePageRenderer, LedgerEvidencePagePorts
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..core.identity.bucket import canonical_bucket_id
from ..domain.attachments.protocols import AttachmentStoreProtocol
from .adapter_composition import build_attachment_store, build_ledger_evidence_ports


def _attachment_store(bucket_id: str, /) -> AttachmentStoreProtocol:
    normalized_bucket_id = canonical_bucket_id(bucket_id)
    if require_active_bucket_id() != normalized_bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return build_attachment_store(normalized_bucket_id)


def build_ledger_evidence_page_operation_ports(
    *, renderer: EvidencePageRenderer | None = None
) -> LedgerEvidencePagePorts:
    """Provide guarded factories and the in-memory renderer; construction opens no profile store."""
    return LedgerEvidencePagePorts(
        evidence_ports_factory=build_ledger_evidence_ports,
        attachment_store_factory=_attachment_store,
        renderer=PageImageRenderer() if renderer is None else renderer,
    )


__all__ = ["build_ledger_evidence_page_operation_ports"]
