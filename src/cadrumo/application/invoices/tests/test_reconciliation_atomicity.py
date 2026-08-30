"""Atomicity contract for the reconciliation write across both catalogues.

Reconciliation is what ESTABLISHES and removes invoice-to-transaction links, so
it is the last place that can afford to persist one side without the other. It
mutates two encrypted catalogues, and written as two independent saves it can
come to rest one-sided -- the invoice citing a transaction that does not cite it
back, or the reverse -- which is precisely what
:func:`~cadrumo.domain.invoices.verify_link_consistency` reports.

The sibling linking writer already commits both together and says why. This
module holds reconciliation to the same contract, using the same instruments: a
real bucket runtime, real adapters, and the production compare-and-swap guard as
the injected fault. Nothing here is stubbed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.invoices.service import verify_link_consistency
from ....domain.iva import InvoiceKind
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from ....tests.write_unit_recorder import WriteUnitRecorder
from .. import reconcile_invoice_catalogues, reconcile_invoice_repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "32323232-3232-4232-8232-323232323232"
_STALE_REVISION_ID = "0" * 64
_AMOUNT = Decimal("121.00")


def _invoice() -> Invoice:
    """One issued invoice whose total matches the seeded transaction."""
    line = InvoiceLine.model_validate(
        {
            "description": "Consultoría",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "REC-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": _AMOUNT,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": (),
            "bucket_id": _BUCKET_ID,
        },
    )


def _transaction() -> Transaction:
    """One incoming transaction the invoice above reconciles against.

    Shaped like the sibling linking fixture, which is the point: reconciliation
    and linking act on the same two catalogues, so their fixtures should not
    disagree about what a persisted transaction looks like.
    """
    raw = RawTransaction(
        provider_transaction_id="bank-row-reconcile-1",
        booked_date=date(2026, 4, 2),
        value_date=date(2026, 4, 2),
        amount=_AMOUNT,
        currency="EUR",
        counterparty="Cliente SL",
        description="Cliente SL",
        provenance=RawProvenance(
            source_path=Path("statement.csv"),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 2, tzinfo=UTC),
            provider_name="csv",
        ),
        raw_fields={"amount": "121.00"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "group_label": "reconcile-atomicity",
            "source_jurisdiction": "ES",
            "notes": "reconciliation atomicity fixture",
            "created_by": "operator",
            "source_command": "aeat app ledger reconcile",
        },
    )


def _seed() -> tuple[Invoice, Transaction]:
    """Persist one unlinked invoice and one unlinked transaction."""
    invoice = _invoice()
    transaction = _transaction()
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(
        TransactionCatalogue.from_transactions([transaction]),
    )
    return invoice, transaction


def test_applying_reconciliation_commits_both_catalogues_in_one_write_transaction(tmp_path: Path) -> None:
    """The applied reconciliation is a single unit of work, not two saves."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed()
        recorder = WriteUnitRecorder(profile.repository.engine)

        with recorder.recording():
            result = reconcile_invoice_repositories(bucket_id=_BUCKET_ID, apply=True)

        assert result.applied >= 1
        assert recorder.commits_between_writes() == 0

        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET_ID).load()
        assert verify_link_consistency(invoices, transactions) == ()


def test_the_recorder_would_notice_a_split_write(tmp_path: Path) -> None:
    """POSITIVE CONTROL, without which the assertion above proves nothing.

    A recorder that reports zero intervening commits for every shape cannot
    discriminate. Driving the two saves separately must report at least one, or
    the atomicity assertion is measuring nothing.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed()
        invoices_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        transactions_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID)
        result = reconcile_invoice_catalogues(invoices_repo.load(), transactions_repo.load(), apply=True)
        recorder = WriteUnitRecorder(profile.repository.engine)

        with recorder.recording():
            invoices_repo.save(result.invoices)
            transactions_repo.save(result.transactions)

        assert recorder.commits_between_writes() >= 1


def test_mid_batch_failure_leaves_neither_catalogue_reconciled(tmp_path: Path) -> None:
    """A failure inside the composed write leaves both sides unlinked.

    The fault is the production compare-and-swap guard: the invoice write
    carries a revision the stored row no longer has, so the conflict is raised
    inside the same unit of work that carries the transaction rows.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        invoice, transaction = _seed()
        invoices_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        transactions_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID)
        result = reconcile_invoice_catalogues(invoices_repo.load(), transactions_repo.load(), apply=True)
        conflicting_invoice_write = invoices_repo.to_secure_object_write(result.invoices).model_copy(
            update={"expected_revision_id": _STALE_REVISION_ID},
        )

        with pytest.raises(SecureObjectRevisionConflictError):
            transactions_repo.save_with_secure_object_writes(
                result.transactions,
                (conflicting_invoice_write,),
            )

        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET_ID).load()
        stored_invoice = invoices.get(invoice.invoice_id)
        stored_transaction = transactions.get(transaction.transaction_id)
        assert stored_invoice is not None
        assert stored_transaction is not None
        assert stored_invoice.linked_transaction_ids == ()
        assert stored_transaction.invoice_id is None
        assert verify_link_consistency(invoices, transactions) == ()
