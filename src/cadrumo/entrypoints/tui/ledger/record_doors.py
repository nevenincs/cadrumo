"""Bucket-bound typed application doors for installed Ledger record detail."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ....adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports
from ....adapters.persistence.profile.catalogue_reads import build_invoice_catalogue_read_ports
from ....application.invoices.catalogue_lifecycle import (
    CatalogueInvoicePatch,
    resolve_catalogue_invoice_from_repository,
    update_catalogue_invoice,
)
from ....application.ledger.actions_manual import get_manual_transaction, update_manual_transaction_fields
from ....application.ledger.models import ManualLedgerTransactionPatch
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import Invoice
from ....domain.transactions.models import Transaction
from ...ledger_action_composition import compose_ledger_action_ports


@dataclass(frozen=True, slots=True)
class LedgerRecordDoors:
    """One captured profile and authority; navigation cannot retarget a write."""

    bucket_id: str
    operation: PinnedAuthorityOperation

    async def invoices(self) -> tuple[Invoice, ...]:
        """List canonical records through the application read port."""
        return await asyncio.to_thread(self._invoices)

    def _invoices(self) -> tuple[Invoice, ...]:
        ports = build_invoice_catalogue_read_ports(bucket_id=self.bucket_id)
        return tuple(sorted(ports.invoice_reader.load().values(), key=lambda item: (item.issued_at, item.invoice_id)))

    async def invoice(self, invoice_id: str) -> Invoice:
        """Resolve one canonical invoice from this door's bucket."""
        return await asyncio.to_thread(self._invoice, invoice_id)

    def _invoice(self, invoice_id: str) -> Invoice:
        return resolve_catalogue_invoice_from_repository(
            invoice_id=invoice_id,
            ports=build_invoice_catalogue_read_ports(bucket_id=self.bucket_id),
        )

    async def update_invoice(self, baseline: Invoice, patch: CatalogueInvoicePatch) -> Invoice:
        """Submit a baseline-guarded metadata patch through the shared writer."""
        return await asyncio.to_thread(self._update_invoice, baseline, patch)

    def _update_invoice(self, baseline: Invoice, patch: CatalogueInvoicePatch) -> Invoice:
        return update_catalogue_invoice(
            bucket_id=self.bucket_id,
            invoice_id=baseline.invoice_id,
            patch=patch,
            ports=build_catalogue_lifecycle_ports(bucket_id=self.bucket_id),
            actor="operator",
            expected_invoice=baseline,
        ).invoice

    async def transaction(self, transaction_id: str) -> Transaction:
        """Resolve one typed transaction through the manual application read."""
        return await asyncio.to_thread(self._transaction, transaction_id)

    def _transaction(self, transaction_id: str) -> Transaction:
        return get_manual_transaction(
            bucket_id=self.bucket_id,
            transaction_id=transaction_id,
            ports=compose_ledger_action_ports(bucket_id=self.bucket_id, operation=self.operation),
        ).transaction

    async def update_transaction(self, baseline: Transaction, patch: ManualLedgerTransactionPatch) -> Transaction:
        """Apply a typed edit to the captured transaction and baseline."""
        return await asyncio.to_thread(self._update_transaction, baseline, patch)

    def _update_transaction(self, baseline: Transaction, patch: ManualLedgerTransactionPatch) -> Transaction:
        return update_manual_transaction_fields(
            bucket_id=self.bucket_id,
            transaction_id=baseline.transaction_id,
            patch=patch,
            actor="operator",
            source_command="tui.ledger.transaction.update",
            ports=compose_ledger_action_ports(bucket_id=self.bucket_id, operation=self.operation),
            expected_current=baseline,
        ).transaction


__all__ = ["LedgerRecordDoors"]
