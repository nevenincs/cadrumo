"""Application-owned capabilities for purchase-invoice evidence.

The evidence service coordinates a bucket catalogue, secure attachment custody,
and bucket-event history.  The concrete encrypted repositories and attachment
manifest service are composed by an executable root and translated into these
narrow application contracts before they reach the service.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ...core.identity.digest import ContentDigest
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol

if TYPE_CHECKING:
    from .evidence import PurchaseInvoiceEvidence


class PurchaseInvoiceEvidenceRepositoryProtocol(Protocol):
    """Bucket-scoped evidence catalogue capability."""

    def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        """Return the evidence records persisted for ``bucket_id``."""
        ...

    def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
        """Persist the complete evidence record set for ``bucket_id``."""
        ...


@dataclass(frozen=True, slots=True)
class EvidenceAttachmentIngestRequest:
    """Application facts needed to place one evidence file in secure custody."""

    bucket_id: str
    source_path: Path
    media_kind: str
    mime_type: str
    captured_at: datetime
    actor: str


class EvidenceAttachmentIngestorProtocol(Protocol):
    """Capability that stores evidence bytes and returns their content address."""

    def ingest(self, request: EvidenceAttachmentIngestRequest) -> ContentDigest:
        """Store the admitted file and return its content-addressed identifier."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerEvidencePorts:
    """Required authorities for one purchase-invoice evidence invocation."""

    evidence_repository: PurchaseInvoiceEvidenceRepositoryProtocol
    attachment_ingestor: EvidenceAttachmentIngestorProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol


class LedgerEvidencePortsFactory(Protocol):
    """Construct the complete evidence bundle for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> LedgerEvidencePorts:
        """Return all evidence capabilities bound to ``bucket_id``."""
        ...


__all__ = [
    "EvidenceAttachmentIngestRequest",
    "EvidenceAttachmentIngestorProtocol",
    "LedgerEvidencePorts",
    "LedgerEvidencePortsFactory",
    "PurchaseInvoiceEvidenceRepositoryProtocol",
]
