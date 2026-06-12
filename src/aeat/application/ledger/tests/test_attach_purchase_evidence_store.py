"""Regression tests pinning the evidence-store id space to the attach/create/update validator.

``aeat app ledger evidence add`` mints a :class:`PurchaseInvoiceEvidence` record
into the dedicated bucket-scoped evidence store, while the purchase-invoice
evidence validator historically resolved only the rich
:class:`InvoiceCatalogue`. These tests assert the validator now accepts an
``evidence add`` id across the attach, create, and update paths — satisfying the
receipt-OCR/PDF-evidence ADR's acceptance criterion (an id produced by
``evidence add`` is accepted by ``aeat app ledger attach`` in the same shell
session, ADR ``2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence``,
2026-05-14 amendment) — while still refusing unknown ids and ids minted by the
slim ``aeat app ledger invoice add`` store (the deliberate store split of ADR
``2026-06-10-ledger-invoice-unification``). Real adapters only: no mocks, stubs,
or monkeypatch (``aeat-quality-gates``, ``aeat-roundtrip-discipline``).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.buckets import BucketEventHistoryRepository
from ....domain.transactions import (
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionValidationError,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import (
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    attach_manual_transaction_evidence,
    create_manual_transaction,
    update_manual_transaction_fields,
)
from .._business_operation_invoice import PayableInvoiceService
from .._evidence import PurchaseInvoiceEvidenceService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "bucket-001"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as runtime:
        yield runtime


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    p = tmp_path / "receipt.pdf"
    p.write_bytes(b"%PDF-1.4 test")
    return p


def _mint_evidence_id(profile: TestRuntimeProfile, pdf_file: Path) -> str:
    """Register a PDF through the real evidence service and return its evidence id."""
    service = PurchaseInvoiceEvidenceService(
        settings=profile.settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
    )
    result = service.add(bucket_id=_BUCKET, source_path=pdf_file)
    return result.record.evidence_id


def _transaction_repository(profile: TestRuntimeProfile) -> TransactionCatalogueRepository:
    return TransactionCatalogueRepository(bucket_id=_BUCKET, objects=profile.repository)


def _event_repository(profile: TestRuntimeProfile) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=profile.repository)


def _create_outgoing_business_transaction(
    profile: TestRuntimeProfile,
    *,
    idempotency_key: str,
    purchase_invoice_evidence_id: str | None = None,
) -> str:
    result = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            idempotency_key=idempotency_key,
        ),
        transaction_repository=_transaction_repository(profile),
        bucket_event_repository=_event_repository(profile),
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    return result.ref.transaction_id


def test_evidence_add_id_is_accepted_by_attach_and_persisted(
    profile: TestRuntimeProfile, pdf_file: Path,
) -> None:
    evidence_id = _mint_evidence_id(profile, pdf_file)
    transaction_id = _create_outgoing_business_transaction(profile, idempotency_key="attach-evidence-add")

    attached = attach_manual_transaction_evidence(
        bucket_id=_BUCKET,
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=evidence_id,
        actor="operator-A",
        transaction_repository=_transaction_repository(profile),
        bucket_event_repository=_event_repository(profile),
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert attached.transaction.purchase_invoice_evidence_id == evidence_id
    # Real save->load assertion: reload the persisted catalogue from storage.
    persisted = _transaction_repository(profile).load().get(transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id == evidence_id


def test_evidence_add_id_is_accepted_by_create(profile: TestRuntimeProfile, pdf_file: Path) -> None:
    evidence_id = _mint_evidence_id(profile, pdf_file)

    transaction_id = _create_outgoing_business_transaction(
        profile,
        idempotency_key="create-evidence-add",
        purchase_invoice_evidence_id=evidence_id,
    )

    persisted = _transaction_repository(profile).load().get(transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id == evidence_id


def test_evidence_add_id_is_accepted_by_update_patch(profile: TestRuntimeProfile, pdf_file: Path) -> None:
    evidence_id = _mint_evidence_id(profile, pdf_file)
    transaction_id = _create_outgoing_business_transaction(profile, idempotency_key="update-evidence-add")

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch(purchase_invoice_evidence_id=evidence_id),
        actor="operator-A",
        source_command="aeat app ledger link",
        transaction_repository=_transaction_repository(profile),
        bucket_event_repository=_event_repository(profile),
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert updated.transaction.purchase_invoice_evidence_id == evidence_id
    persisted = _transaction_repository(profile).load().get(transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id == evidence_id


def test_nonexistent_evidence_id_is_refused_with_instructive_message(profile: TestRuntimeProfile) -> None:
    transaction_id = _create_outgoing_business_transaction(profile, idempotency_key="attach-unknown")

    with pytest.raises(TransactionValidationError) as exc_info:
        attach_manual_transaction_evidence(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            purchase_invoice_evidence_id="deadbeef00000000",
            actor="operator-A",
            transaction_repository=_transaction_repository(profile),
            bucket_event_repository=_event_repository(profile),
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    # The acceptance is store-backed, not unconditional: an absent record still refuses,
    # and the refusal names the canonical evidence-registration verb.
    assert "aeat app ledger evidence add" in str(exc_info.value)


def test_slim_invoice_add_id_is_refused_by_attach(profile: TestRuntimeProfile) -> None:
    # An id minted by the slim operator invoice CRUD (`aeat app ledger invoice add`)
    # is NOT a valid evidence reference per the ledger-invoice unification ADR's
    # store split (`2026-06-10-ledger-invoice-unification`); attach must refuse it.
    invoice_service = PayableInvoiceService(
        settings=profile.settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
    )
    slim_invoice = invoice_service.add(
        bucket_id=_BUCKET,
        counterparty_nif="B12345678",
        invoice_number="INV-2026-001",
        invoice_date="2026-05-01",
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        total_amount=Decimal("121.00"),
    )
    transaction_id = _create_outgoing_business_transaction(profile, idempotency_key="attach-slim-invoice")

    with pytest.raises(TransactionValidationError) as exc_info:
        attach_manual_transaction_evidence(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=slim_invoice.record.invoice_id,
            actor="operator-A",
            transaction_repository=_transaction_repository(profile),
            bucket_event_repository=_event_repository(profile),
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    assert "aeat app ledger invoice add" in str(exc_info.value)
