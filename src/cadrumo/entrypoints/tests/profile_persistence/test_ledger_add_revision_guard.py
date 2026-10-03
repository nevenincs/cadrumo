"""Manual ledger add preserves concurrent secure rows when its snapshot is stale."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql.secure_object_records import (
    SecureObjectDeletion,
    SecureObjectRevisionAssertion,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.ledger.action_ports import LedgerActionPorts
from ....application.ledger.actions_manual import create_manual_transaction
from ....application.ledger.models import ManualLedgerTransactionCommand
from ....application.ledger.persistence_ports import LedgerPersistenceConflictError
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.usage_ratios.model import UsageRatioProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 4, 15, 9, 30, tzinfo=UTC)


def _manual_command(bucket_id: str, description: str) -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand(
        bucket_id=bucket_id,
        booked_date=date(2026, 4, 15),
        amount=Decimal("10.00"),
        direction=TransactionDirection.OUTGOING,
        description=description,
        business_classification=BusinessClassification.PERSONAL,
        actor="operator",
        source_command="aeat app ledger add",
    )


def _concurrent_row() -> Transaction:
    """Build an unrelated persisted row from public domain facts."""
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="concurrent-unrelated-row",
                booked_date=date(2026, 4, 15),
                value_date=date(2026, 4, 15),
                amount=Decimal("10.00"),
                currency="EUR",
                counterparty="Synthetic counterparty",
                description="concurrent unrelated row",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=_NOW,
                    provider_name="manual",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.PERSONAL,
            "business_pct": None,
            "source_jurisdiction": "ES",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        }
    )


def test_guarded_manual_add_conflicts_without_erasing_a_concurrent_secure_row(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A concurrent unrelated secure-row addition survives the add CAS conflict."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="33333333-3333-4333-8333-333333333333") as profile:
        transactions = TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository)
        events = BucketEventHistoryRepository(objects=profile.repository)
        ports = LedgerActionPorts(
            operation=operation,
            transaction_repository=transactions,
            bucket_event_repository=events,
            invoice_repository=InvoiceCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository),
            attachment_store=AttachmentStore(bucket_id=profile.bucket_id, objects=profile.repository),
            usage_ratio_profile=UsageRatioProfile(),
            usage_ratio_profile_loader=lambda **_kwargs: UsageRatioProfile(),
            work_unit_repository=WorkUnitCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository),
            calculation_repository=CalculationRevisionCatalogueRepository(
                bucket_id=profile.bucket_id,
                objects=profile.repository,
            ),
            purchase_invoice_evidence_records=(),
        )
        add_command = _manual_command(profile.bucket_id, "worker add")
        events_before = events.load()
        concurrent = _concurrent_row()
        original_apply_batch = profile.repository.apply_batch
        raced = False

        def add_row_before_asserted_commit(
            writes: tuple[SecureObjectWrite, ...],
            deletions: tuple[SecureObjectDeletion, ...] = (),
            *,
            assertions: tuple[SecureObjectRevisionAssertion, ...] = (),
        ) -> None:
            nonlocal raced
            if assertions and not raced:
                raced = True
                transactions.save(TransactionCatalogue.from_transactions((concurrent,)))
            original_apply_batch(writes, deletions, assertions=assertions)

        monkeypatch.setattr(profile.repository, "apply_batch", add_row_before_asserted_commit)
        with pytest.raises(LedgerPersistenceConflictError):
            create_manual_transaction(
                add_command,
                ports=ports,
                occurred_at=_NOW,
                require_revision_guard=True,
            )

        saved = transactions.load()
        stored_events = events.load()

    assert raced
    assert set(saved.transactions) == {concurrent.transaction_id}
    assert stored_events == events_before
