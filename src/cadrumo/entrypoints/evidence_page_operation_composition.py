"""Concrete evidence catalogue, attachment custody and renderer for the page read."""

from __future__ import annotations

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..adapters.inbound.einvoice.xml import MAX_XML_PAYLOAD_BYTES
from ..application.ledger.evidence_page_contracts import (
    EvidencePageMediaType,
    EvidencePageRenderer,
    LedgerEvidencePagePorts,
    RenderedEvidencePage,
)
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..core.identity.bucket import canonical_bucket_id
from ..domain.attachments.protocols import AttachmentStoreProtocol
from .adapter_composition import build_attachment_store, build_ledger_evidence_ports


class _DeferredPageRenderer:
    """The page renderer, whose image and PDF engines load on the first page drawn.

    Building the operation registry must not load them: only the worker that
    draws a page needs them.
    """

    def __init__(self) -> None:
        self._renderer: EvidencePageRenderer | None = None

    @property
    def max_source_bytes(self) -> int:
        """The largest document, in bytes, the renderer accepts."""
        return MAX_XML_PAYLOAD_BYTES

    def render(
        self,
        source: bytes,
        *,
        media_type: EvidencePageMediaType,
        page: int,
        max_width: int,
        max_image_bytes: int,
    ) -> RenderedEvidencePage:
        """Draw page ``page`` (1-based) of ``source`` with the engines loaded now."""
        if self._renderer is None:
            from ..adapters.inbound.pdf.page_image import PageImageRenderer

            self._renderer = PageImageRenderer()
        return self._renderer.render(
            source, media_type=media_type, page=page, max_width=max_width, max_image_bytes=max_image_bytes
        )


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
        renderer=_DeferredPageRenderer() if renderer is None else renderer,
    )


__all__ = ["build_ledger_evidence_page_operation_ports"]
