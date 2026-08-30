"""Atomicity contract for the bidirectional invoice-to-transaction link write.

:func:`link_invoice_transaction_repositories` mutates two encrypted
catalogues at once. Written as two independent saves it can come to rest
one-sided -- the invoice citing a transaction that does not cite it back, or
the reverse -- which is precisely what
:func:`~cadrumo.domain.invoices.verify_link_consistency` reports. These tests
pin the write to a single unit of work using real adapters throughout: a real
:class:`~cadrumo.tests.master_key.EphemeralMasterKeyProvider`, a real
SQLite-backed
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`, and the
production serializers. Nothing here is stubbed; the failure injected in
:func:`test_mid_batch_failure_rolls_back_both_catalogues` is the same
compare-and-swap revision guard production uses.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from ....core import LinkInconsistencyDirection
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.invoices.service import verify_link_consistency
from ....domain.iva.classification import InvoiceKind
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from ....tests.write_unit_recorder import WriteUnitRecorder
from .. import link_invoice_transaction_catalogues, link_invoice_transaction_repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "31313131-3131-4131-8131-313131313131"
_STALE_REVISION_ID = "0" * 64


def test_link_commits_both_catalogues_in_one_write_transaction(tmp_path: Path) -> None:
    """The link's two catalogue writes land inside a single transaction.

    A commit falling between them is the seam a crash exploits: whichever
    catalogue committed first would keep its half of the link.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice, transaction = _seed(profile.bucket_id)
        recorder = WriteUnitRecorder(profile.repository.engine)

        with recorder.recording():
            link_invoice_transaction_repositories(
                bucket_id=profile.bucket_id,
                invoice_id=invoice.invoice_id,
                transaction_id=transaction.transaction_id,
            )

        assert recorder.commits_between_writes() == 0

        invoices = InvoiceCatalogueRepository(bucket_id=profile.bucket_id).load()
        transactions = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        assert verify_link_consistency(invoices, transactions) == ()


def test_split_write_shape_commits_between_the_two_catalogues(tmp_path: Path) -> None:
    """Anti-tautology: the recorder does detect a seam when one exists.

    Persisting the same linked catalogues through two independent saves --
    the shape this writer replaced -- must be observed as two transactions.
    Without this, a recorder that could never report a non-zero count would
    make the assertion above vacuous.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice, transaction = _seed(profile.bucket_id)
        invoices_repo = InvoiceCatalogueRepository(bucket_id=profile.bucket_id)
        transactions_repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        result = link_invoice_transaction_catalogues(
            invoices_repo.load(),
            transactions_repo.load(),
            invoice_id=invoice.invoice_id,
            transaction_id=transaction.transaction_id,
        )
        recorder = WriteUnitRecorder(profile.repository.engine)

        with recorder.recording():
            invoices_repo.save(result.invoices)
            transactions_repo.save(result.transactions)

        assert recorder.commits_between_writes() >= 1


def test_mid_batch_failure_rolls_back_both_catalogues(tmp_path: Path) -> None:
    """A failure inside the composed write leaves neither catalogue linked.

    The fault is the production compare-and-swap guard: the invoice write
    carries a revision id that no longer matches the stored row, so the
    conflict is raised inside the same unit of work that carries the
    transaction rows. Both sides must roll back together.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice, transaction = _seed(profile.bucket_id)
        invoices_repo = InvoiceCatalogueRepository(bucket_id=profile.bucket_id)
        transactions_repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        result = link_invoice_transaction_catalogues(
            invoices_repo.load(),
            transactions_repo.load(),
            invoice_id=invoice.invoice_id,
            transaction_id=transaction.transaction_id,
        )
        conflicting_invoice_write = invoices_repo.to_secure_object_write(result.invoices).model_copy(
            update={"expected_revision_id": _STALE_REVISION_ID},
        )

        with pytest.raises(SecureObjectRevisionConflictError):
            transactions_repo.save_with_secure_object_writes(
                result.transactions,
                (conflicting_invoice_write,),
            )

        invoices = InvoiceCatalogueRepository(bucket_id=profile.bucket_id).load()
        transactions = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        stored_invoice = invoices.get(invoice.invoice_id)
        stored_transaction = transactions.get(transaction.transaction_id)
        assert stored_invoice is not None
        assert stored_transaction is not None
        assert stored_invoice.linked_transaction_ids == ()
        assert stored_transaction.invoice_id is None
        assert verify_link_consistency(invoices, transactions) == ()


def test_link_roundtrips_every_populated_field_through_both_catalogues(tmp_path: Path) -> None:
    """The committed catalogues reload strictly equal to what the link produced.

    Both records carry non-default values in every optional field the link
    does not itself touch, so a field dropped by the co-commit serialisation
    surfaces as inequality rather than hiding behind a default.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice, transaction = _seed(profile.bucket_id)

        result = link_invoice_transaction_repositories(
            bucket_id=profile.bucket_id,
            invoice_id=invoice.invoice_id,
            transaction_id=transaction.transaction_id,
        )

        invoices = InvoiceCatalogueRepository(bucket_id=profile.bucket_id).load()
        transactions = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        assert invoices.get(invoice.invoice_id) == result.invoices.get(invoice.invoice_id)
        assert transactions.get(transaction.transaction_id) == result.transactions.get(transaction.transaction_id)


def test_one_sided_link_on_disk_is_reported_as_inconsistent(tmp_path: Path) -> None:
    """Anti-tautology: a half-written link is detected, not silently accepted.

    Rewriting only the invoice catalogue reproduces the divergence the split
    write shape could leave behind. The equality assertion above is only
    meaningful if this state is distinguishable, and the detector the CLI
    exposes must name it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice, transaction = _seed(profile.bucket_id)
        result = link_invoice_transaction_repositories(
            bucket_id=profile.bucket_id,
            invoice_id=invoice.invoice_id,
            transaction_id=transaction.transaction_id,
        )

        # Roll the transaction side back to its unlinked form, leaving the
        # invoice side citing it: the exact one-sided state a torn write leaves.
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions([transaction]),
        )

        invoices = InvoiceCatalogueRepository(bucket_id=profile.bucket_id).load()
        transactions = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        assert transactions.get(transaction.transaction_id) != result.transactions.get(transaction.transaction_id)
        inconsistencies = verify_link_consistency(invoices, transactions)
        assert len(inconsistencies) == 1
        assert inconsistencies[0].invoice_id == invoice.invoice_id
        assert inconsistencies[0].transaction_id == transaction.transaction_id
        assert inconsistencies[0].direction is LinkInconsistencyDirection.INVOICE_ONLY


def _seed(bucket_id: str) -> tuple[Invoice, Transaction]:
    """Persist one unlinked invoice and one unlinked transaction."""
    invoice = _invoice()
    transaction = _transaction()
    InvoiceCatalogueRepository(bucket_id=bucket_id).save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository(bucket_id=bucket_id).save(TransactionCatalogue.from_transactions([transaction]))
    return invoice, transaction


def _invoice() -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-ATOMIC-1",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "notes": "atomicity fixture",
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Servicios",
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100.00"),
                        "subtotal": Decimal("100.00"),
                        "iva_rate": IvaRate.RATE_21,
                        "iva_amount": Decimal("21.00"),
                    },
                ),
            ),
        },
    )


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="bank-row-atomic-1",
        booked_date=date(2026, 4, 2),
        value_date=date(2026, 4, 2),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Cliente SL",
        description="Cliente SL",
        provenance=RawProvenance(
            source_path=Path("statement.csv"),
            source_sha256="b" * 64,
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
            "group_label": "atomicity",
            "source_jurisdiction": "ES",
            "notes": "atomicity fixture",
            "created_by": "operator",
            "source_command": "aeat app ledger link",
        },
    )
