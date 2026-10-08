"""Exact-profile capabilities for canonical batch evidence ingestion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...core.config import Settings
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .evidence_ports import LedgerEvidencePorts
from .extraction_draft_repository import ExtractionDraftRepositoryFactory
from .invoice_draft_extraction_ports import InvoiceDraftExtractionPorts


@dataclass(frozen=True, slots=True)
class LedgerEvidenceIngestionPorts:
    """One immutable worker binding and its existing canonical capabilities."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    settings: Settings
    evidence: LedgerEvidencePorts
    extraction: InvoiceDraftExtractionPorts
    draft_factory: ExtractionDraftRepositoryFactory


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
