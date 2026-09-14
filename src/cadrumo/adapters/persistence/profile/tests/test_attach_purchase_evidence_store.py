"""Regression tests pinning the evidence-store id space to the attach/create/update validator.

``aeat app ledger evidence add`` mints a :class:`PurchaseInvoiceEvidence` record
into the dedicated bucket-scoped evidence store, while the purchase-invoice
evidence validator historically resolved only the rich
:class:`InvoiceCatalogue`. These tests assert the validator now accepts an
``evidence add`` id across the attach, create, and update paths — an id produced
by ``evidence add`` is accepted by ``aeat app ledger attach`` in the same shell
session — while still refusing unknown ids and ids minted by the slim
``aeat app ledger invoice add`` store (the deliberate evidence/invoice store
split). Real adapters only: no mocks, stubs, or monkeypatch
(``aeat-quality-gates``, ``aeat-quality-gates``).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ._evidence_test_support import _make_svc, pdf_file

__all__ = ["pdf_file"]

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    create_manual_transaction,
    update_manual_transaction_fields,
)
from cadrumo.application.ledger.models import (
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.errors import TransactionValidationError

from .ledger_action_create_support import ledger_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "31313131-3131-4131-8131-313131313131"


def _create_manual_transaction(
    profile: TestRuntimeProfile,
    command: Any,
    **kwargs: Any,
) -> ManualLedgerTransactionResult:
    transaction_repository = kwargs.pop("transaction_repository")
    bucket_event_repository = kwargs.pop("bucket_event_repository")
    with ledger_ports_for_test(
        bucket_id=command.bucket_id,
        objects=profile.repository,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
    ) as ports:
        return create_manual_transaction(command, ports=ports, **kwargs)


def _attach_manual_transaction_evidence(
    profile: TestRuntimeProfile,
    **kwargs: Any,
) -> ManualLedgerTransactionResult:
    transaction_repository = kwargs.pop("transaction_repository")
    bucket_event_repository = kwargs.pop("bucket_event_repository")
    with ledger_ports_for_test(
        bucket_id=kwargs["bucket_id"],
        objects=profile.repository,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
    ) as ports:
        return attach_manual_transaction_evidence(ports=ports, **kwargs)


def _update_manual_transaction_fields(
    profile: TestRuntimeProfile,
    **kwargs: Any,
) -> ManualLedgerTransactionResult:
    transaction_repository = kwargs.pop("transaction_repository")
    bucket_event_repository = kwargs.pop("bucket_event_repository")
    with ledger_ports_for_test(
        bucket_id=kwargs["bucket_id"],
        objects=profile.repository,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
    ) as ports:
        return update_manual_transaction_fields(ports=ports, **kwargs)


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as runtime:
        yield runtime


def _mint_evidence_id(profile: TestRuntimeProfile, pdf_file: Path) -> str:
    """Register a PDF through the real evidence service and return its evidence id."""
    service = _make_svc(profile.settings, profile.repository)
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
    result = _create_manual_transaction(
        profile,
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
    profile: TestRuntimeProfile,
    pdf_file: Path,
) -> None:
    evidence_id = _mint_evidence_id(profile, pdf_file)
    transaction_id = _create_outgoing_business_transaction(profile, idempotency_key="attach-evidence-add")

    attached = _attach_manual_transaction_evidence(
        profile,
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


def test_generic_update_patch_refuses_evidence_field(profile: TestRuntimeProfile, pdf_file: Path) -> None:
    # The generic manual-field update door no longer accepts evidence: evidence
    # catalogue and provenance mutation are reserved for `aeat app ledger attach`.
    # A patch that sets purchase_invoice_evidence_id is refused, and the on-disk
    # transaction stays evidence-free.
    evidence_id = _mint_evidence_id(profile, pdf_file)
    transaction_id = _create_outgoing_business_transaction(profile, idempotency_key="update-evidence-add")

    with pytest.raises(TransactionValidationError) as exc_info:
        _update_manual_transaction_fields(
            profile,
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(purchase_invoice_evidence_id=evidence_id),
            actor="operator-A",
            source_command="aeat app ledger link",
            transaction_repository=_transaction_repository(profile),
            bucket_event_repository=_event_repository(profile),
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    assert "aeat app ledger attach" in str(exc_info.value)
    persisted = _transaction_repository(profile).load().get(transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id is None


def test_nonexistent_evidence_id_is_refused_with_instructive_message(profile: TestRuntimeProfile) -> None:
    transaction_id = _create_outgoing_business_transaction(profile, idempotency_key="attach-unknown")

    with pytest.raises(TransactionValidationError) as exc_info:
        _attach_manual_transaction_evidence(
            profile,
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


def test_invoice_id_is_refused_by_attach(profile: TestRuntimeProfile) -> None:
    # An invoice id (minted by `aeat app ledger invoice add`) is NOT a valid
    # evidence reference under the evidence/invoice store split; attach must
    # refuse it. The two id spaces stay distinct even though both are
    # content-addressed 64-hex digests, so the refusal cannot lean on shape.
    from cadrumo.domain.invoices.models import derive_invoice_id
    from cadrumo.domain.iva.classification import InvoiceKind

    invoice_id = derive_invoice_id(
        kind=InvoiceKind.RECEIVED,
        invoice_number="INV-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="B12345674",
        currency="EUR",
        grand_total=Decimal("121.00"),
    )
    transaction_id = _create_outgoing_business_transaction(profile, idempotency_key="attach-slim-invoice")

    with pytest.raises(TransactionValidationError) as exc_info:
        _attach_manual_transaction_evidence(
            profile,
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=invoice_id,
            actor="operator-A",
            transaction_repository=_transaction_repository(profile),
            bucket_event_repository=_event_repository(profile),
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    assert "aeat app ledger invoice add" in str(exc_info.value)
