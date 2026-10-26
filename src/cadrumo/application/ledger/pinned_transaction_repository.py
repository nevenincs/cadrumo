"""One COMMIT-loaded transaction catalogue snapshot pinned to its revision."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from ...core.secure_object_write import SecureObjectWrite
from ...domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from .persistence_ports import LedgerPersistenceConflictError
from .protocols import RevisionGuardedTransactionCatalogueCoCommitWriterProtocol


@dataclass(frozen=True, slots=True)
class PinnedRevisionedTransactionRepository:
    """Expose one already-loaded catalogue and force its whole-catalogue compare-and-swap.

    A ledger action that resolved its targets against ``catalogue`` must commit
    against exactly ``revision_id``: every other write path refuses, so a
    concurrent change surfaces as a persistence conflict rather than a write
    against a newer snapshot. ``action`` names the ledger action in that refusal.
    """

    repository: RevisionGuardedTransactionCatalogueCoCommitWriterProtocol
    catalogue: TransactionCatalogue
    revision_id: str
    action: str

    @property
    def bucket_id(self) -> str:
        """Return the pinned repository's profile bucket."""
        return self.repository.bucket_id

    def exists(self) -> bool:
        """Report whether the underlying catalogue exists."""
        return self.repository.exists()

    def load(self) -> TransactionCatalogue:
        """Return the pinned snapshot, never a fresh read."""
        return self.catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        """Read a date window from the underlying repository."""
        return self.repository.load_for_date_range(start, end)

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Read named transactions from the underlying repository."""
        return self.repository.load_by_ids(transaction_ids)

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Partition the underlying catalogue around a date window."""
        return self.repository.partition_by_date_range(start, end)

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Refuse an unrevisioned whole-catalogue write.

        Parameter types: ``catalogue`` (:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`).
        """
        _ = catalogue
        raise self._unpinned_write()

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Refuse an unrevisioned write with secure objects.

        Parameter types: ``catalogue`` (:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`).
        """
        _ = catalogue, extra_writes
        raise self._unpinned_write()

    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Refuse a single-transaction replacement outside the pinned revision."""
        _ = current, replacement, extra_writes
        raise self._unpinned_write()

    def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
        """Return the pinned snapshot with its revision."""
        return self.catalogue, self.revision_id

    def save_if_revision_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        *,
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Commit only against the pinned revision.

        Parameter types: ``catalogue`` (:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`).
        """
        if expected_revision_id != self.revision_id:
            raise LedgerPersistenceConflictError(f"ledger {self.action} attempted to write against another snapshot")
        self.repository.save_if_revision_with_secure_object_writes(
            catalogue,
            expected_revision_id=self.revision_id,
            extra_writes=extra_writes,
        )

    def _unpinned_write(self) -> LedgerPersistenceConflictError:
        return LedgerPersistenceConflictError(f"ledger {self.action} requires the pinned catalogue revision")
