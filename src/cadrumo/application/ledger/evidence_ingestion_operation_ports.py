"""Exact-profile capabilities for canonical batch and Drive evidence ingestion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...core.config import Settings
from ...domain.attachments.enums import AttachmentSource
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .action_ports import LedgerActionPorts
from .evidence_ports import LedgerEvidencePorts
from .evidence_sweep_ports import EvidenceSweepDocument
from .extraction_draft_store import ExtractionDraftRepositoryFactory
from .invoice_draft_extraction_ports import InvoiceDraftExtractionPorts


@dataclass(frozen=True, slots=True)
class EvidenceAcquisitionListing:
    """Canonical ordered document listing with its non-document count."""

    folder_id: str
    documents: tuple[EvidenceSweepDocument, ...]
    skipped_non_document_count: int


class EvidenceAcquisitionPort(Protocol):
    """Scope-preserving byte acquisition; credentials stay behind this port."""

    def fetch(self, *, source: AttachmentSource, reference: str) -> bytes:
        """Fetch one reachable document under current request authority."""
        ...

    def list_folder(self, reference: str) -> EvidenceAcquisitionListing:
        """Resolve and list the supported documents in one Drive folder."""
        ...

    def fetch_folder_document(self, document: EvidenceSweepDocument) -> bytes:
        """Fetch a listed child, translating only its scope refusal."""
        ...

    def mime_type(self, reference: str, data: bytes) -> str:
        """Return canonical provenance MIME metadata without filtering bytes."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerEvidenceIngestionPorts:
    """One immutable worker binding and its existing canonical capabilities."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    settings: Settings
    evidence: LedgerEvidencePorts
    extraction: InvoiceDraftExtractionPorts
    draft_factory: ExtractionDraftRepositoryFactory
    actions: LedgerActionPorts
    attachment_store: AttachmentStoreProtocol
    acquisition: EvidenceAcquisitionPort


class LedgerEvidenceIngestionPortsFactory(Protocol):
    """Compose all ingestion capabilities after checking the immutable worker pin."""

    def __call__(
        self,
        *,
        profile_id: UUID,
        operation: PinnedAuthorityOperation,
        mutation_writer: Callable[[Callable[[], None]], None],
        before_read: Callable[[], None],
    ) -> LedgerEvidenceIngestionPorts:
        """Bind actual custody writes and outbound admission to this operation."""
        ...
