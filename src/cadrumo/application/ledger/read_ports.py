"""Exact-profile repositories needed to select ledger rows and their history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .protocols import BucketEventHistoryCoCommitWriterProtocol, TransactionCatalogueCoCommitWriterProtocol


@dataclass(frozen=True)
class LedgerReadPorts:
    """Read composition without invoice, calculation or evidence hydration."""

    operation: PinnedAuthorityOperation
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol


class LedgerReadPortsFactory(Protocol):
    """Bind the read repositories to the admitted profile and authority."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerReadPorts:
        """Return repositories for one admitted read."""
        ...
