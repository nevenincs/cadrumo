"""In-memory co-commit transaction port shared by ledger application tests."""

from __future__ import annotations

from typing import override

from ....core.secure_object_write import SecureObjectWrite
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...tests.ledger_partition_support import CatalogueTransactionRepository
from ..protocols import TransactionCatalogueCoCommitWriterProtocol


class InMemoryTransactionRepository(CatalogueTransactionRepository, TransactionCatalogueCoCommitWriterProtocol):
    """Hold one catalogue and honour guarded replacement against its current rows.

    Read-only callers keep ``permit_secure_object_writes`` off, so any attempt to
    co-commit secure objects through the port fails loudly. Write-path callers
    turn it on and the extra objects are discarded.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        catalogue: TransactionCatalogue,
        permit_secure_object_writes: bool = False,
    ) -> None:
        super().__init__(bucket_id=bucket_id, catalogue=catalogue)
        self._permit_secure_object_writes = permit_secure_object_writes

    def _refuse_unpermitted_writes(self, extra_writes: tuple[SecureObjectWrite, ...]) -> None:
        if extra_writes and not self._permit_secure_object_writes:
            raise AssertionError("this transaction fake does not support secure-object writes")

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        self._refuse_unpermitted_writes(extra_writes)
        self.save(catalogue)

    @override
    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        self._refuse_unpermitted_writes(extra_writes)
        if self._catalogue.get(current.transaction_id) != current:
            raise AssertionError("guarded replacement received a stale baseline")
        updated = dict(self._catalogue.transactions)
        updated.pop(current.transaction_id)
        updated[replacement.transaction_id] = replacement
        self._catalogue = TransactionCatalogue.from_transactions(updated.values())
