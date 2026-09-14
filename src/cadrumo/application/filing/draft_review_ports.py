"""Application-owned capabilities for draft approval and stale detection.

The draft-review lifecycle fingerprints several persisted authorities.  This
module keeps that use case independent from the encrypted-storage adapters and
gives composition roots one cohesive bundle to bind for a profile bucket.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ...domain.filing.schema import ModeloDraft
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol


class DraftReviewProfileRepositoryProtocol(Protocol):
    """Read-only profile projection used by the approval-basis fingerprint."""

    def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
        """Return canonical profile path values, or ``None`` when absent."""
        ...


class DraftReviewDraftRepositoryProtocol(Protocol):
    """Read-only draft store capability used by the review queue."""

    def iter_drafts(self) -> Iterator[ModeloDraft]:
        """Yield the bucket's persisted drafts."""
        ...

    def envelope_path_for(self, identifier: str) -> Path:
        """Return the non-secret logical path marker for one draft."""
        ...


@dataclass(frozen=True, slots=True)
class DraftReviewPorts:
    """Required persisted authorities for one draft-review invocation."""

    transaction_repository: TransactionCatalogueRepositoryProtocol
    invoice_repository: InvoiceCatalogueRepositoryProtocol
    observation_repository: CalculationObservationRepositoryProtocol
    profile_repository: DraftReviewProfileRepositoryProtocol
    draft_repository: DraftReviewDraftRepositoryProtocol


class DraftReviewPortsFactory(Protocol):
    """Construct the draft-review authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> DraftReviewPorts:
        """Return all capabilities required for ``bucket_id``."""
        ...


__all__ = [
    "DraftReviewPorts",
    "DraftReviewPortsFactory",
    "DraftReviewDraftRepositoryProtocol",
    "DraftReviewProfileRepositoryProtocol",
]
