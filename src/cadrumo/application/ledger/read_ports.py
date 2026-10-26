"""Exact-profile repositories needed to select ledger rows and their history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.transactions.models import TransactionCatalogue
    from .protocols import BucketEventHistoryCoCommitWriterProtocol, TransactionCatalogueCoCommitWriterProtocol


@dataclass(frozen=True)
class LedgerReadPorts:
    """Read composition without invoice, calculation or evidence hydration."""

    operation: PinnedAuthorityOperation
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol


class FullyValidatedTransactionCatalogueReader(Protocol):
    """Read one profile's whole transaction catalogue with every admission check re-run.

    An ordinary catalogue read trusts the secure store's binding for each row's
    id; this read re-derives it too, so a stored row that no longer satisfies
    admission is refused rather than read.
    """

    @property
    def bucket_id(self) -> str:
        """Return the profile bucket the reader is bound to."""
        ...

    def load_fully_validated(self) -> TransactionCatalogue:
        """Return the catalogue after validating every row in full.

        Core types: :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
        """
        ...


class LedgerReadPortsFactory(Protocol):
    """Bind the read repositories to the admitted profile and authority."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerReadPorts:
        """Return repositories for one admitted read."""
        ...
