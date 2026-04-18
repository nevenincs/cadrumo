"""Pydantic shape + invariant tests for the review-queue models."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from ..filing import FilingFindingSeverity, FilingValidationFinding
from ..financial import RawProvenance, RawTransaction, SourceFormat
from ..financial.invoices import (
    Invoice,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ..financial.transactions import BusinessClassification, Transaction, TransactionDirection
from ..i18n import Translatable
from ..inbox import Notificacion, NotificacionKind, NotificacionPriority
from ..sync import (
    CasillaAddedWithDefault,
    DivergenceClassification,
    DivergenceRecord,
    ModeloIdentifier,
)
from . import (
    DivergenceReviewItem,
    FindingReviewItem,
    InboxReviewItem,
    InvoiceReviewItem,
    ReviewItem,
    ReviewItemKind,
    ReviewSeverity,
    TransactionReviewItem,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


_REVIEW_ITEM_ADAPTER = TypeAdapter(ReviewItem)


def _summary(text: str = "demo") -> Translatable:
    return {"es": text, "en": text, "hu": text}


def _raw() -> RawTransaction:
    return RawTransaction(
        transaction_id="prov-1",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("12.34"),
        currency="EUR",
        counterparty="Acme",
        description="Office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="csv",
        ),
        raw_fields={"Concepto": "Office supplies"},
    )


def _transaction() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.UNCLASSIFIED,
        }
    )


def _invoice_line() -> InvoiceLine:
    return InvoiceLine(
        description="Consultoría",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )


def _invoice() -> Invoice:
    line = _invoice_line()
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": (),
        }
    )


def _divergence() -> DivergenceRecord:
    modelo = ModeloIdentifier("130")
    payload = CasillaAddedWithDefault(
        modelo=modelo,
        casilla_id="C9",
        default="0",
        label=_summary("label"),
    )
    return DivergenceRecord(
        record_id=uuid.uuid4().hex,
        detected_at=datetime(2026, 4, 12, tzinfo=UTC),
        modelo=modelo,
        classification=DivergenceClassification.ADDITIVE,
        payload=payload,
    )


def _finding() -> FilingValidationFinding:
    return FilingValidationFinding(
        casilla_id="03",
        severity=FilingFindingSeverity.ERROR,
        code="casilla-out-of-range",
        message=_summary("range error"),
    )


def _notificacion() -> Notificacion:
    received = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    return Notificacion(
        notificacion_id="AEAT-0001",
        kind=NotificacionKind.REQUERIMIENTO,
        priority=NotificacionPriority.CRITICAL,
        subject=_summary("subject"),
        body_excerpt=_summary("body"),
        received_at=received,
        effective_at=received,
        appeal_deadline=date(2026, 4, 20),
        source_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/notif/x"),
    )


def test_transaction_review_item_round_trips_through_json() -> None:
    item = TransactionReviewItem(
        item_id="t-1",
        modelo=None,
        severity=ReviewSeverity.NORMAL,
        summary=_summary("tx"),
        drill_command="aeat financial txs classify t-1 --as ...",
        since=datetime(2026, 4, 10, tzinfo=UTC),
        source=_transaction(),
    )
    restored = TransactionReviewItem.model_validate_json(item.model_dump_json())
    assert restored == item
    assert restored.kind is ReviewItemKind.TRANSACTION


def test_review_item_discriminator_resolves_each_kind() -> None:
    payloads = [
        TransactionReviewItem(
            item_id="t-1",
            modelo=None,
            severity=ReviewSeverity.NORMAL,
            summary=_summary("tx"),
            drill_command="aeat financial txs classify t-1 --as ...",
            since=datetime(2026, 4, 10, tzinfo=UTC),
            source=_transaction(),
        ),
        InvoiceReviewItem(
            item_id="i-1",
            modelo=None,
            severity=ReviewSeverity.HIGH,
            summary=_summary("inv"),
            drill_command="aeat financial invoices show i-1",
            since=datetime(2026, 4, 1, tzinfo=UTC),
            source=_invoice(),
        ),
        DivergenceReviewItem(
            item_id="d-1",
            modelo="130",
            severity=ReviewSeverity.NORMAL,
            summary=_summary("div"),
            drill_command="aeat sync show-divergence d-1",
            since=datetime(2026, 4, 12, tzinfo=UTC),
            source=_divergence(),
        ),
        FindingReviewItem(
            item_id="f-1",
            modelo="130",
            severity=ReviewSeverity.CRITICAL,
            summary=_summary("finding"),
            drill_command="aeat filing show /tmp/d.json --findings-only",
            since=datetime(2026, 4, 14, tzinfo=UTC),
            source=_finding(),
            draft_id="draft-1",
            draft_path="draft.json",
        ),
        InboxReviewItem(
            item_id="n-1",
            modelo=None,
            severity=ReviewSeverity.CRITICAL,
            summary=_summary("inbox"),
            drill_command="aeat inbox show n-1",
            since=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            source=_notificacion(),
        ),
    ]
    for original in payloads:
        restored = _REVIEW_ITEM_ADAPTER.validate_json(original.model_dump_json())
        assert restored.kind is original.kind
        assert restored == original


def test_finding_review_item_allows_none_source_for_placeholder_row() -> None:
    placeholder = FindingReviewItem(
        item_id="draft-1:_status:VALIDATED",
        modelo="130",
        severity=ReviewSeverity.NORMAL,
        summary=_summary("draft not ready"),
        drill_command="aeat filing show /tmp/d.json",
        since=datetime(2026, 4, 14, tzinfo=UTC),
        source=None,
        draft_id="draft-1",
        draft_path="draft.json",
    )
    restored = FindingReviewItem.model_validate_json(placeholder.model_dump_json())
    assert restored.source is None


def test_review_item_rejects_naive_since_timestamp() -> None:
    with pytest.raises(ValidationError):
        TransactionReviewItem(
            item_id="t-1",
            modelo=None,
            severity=ReviewSeverity.NORMAL,
            summary=_summary("tx"),
            drill_command="aeat financial txs classify t-1 --as ...",
            since=datetime(2026, 4, 10),
            source=_transaction(),
        )


def test_review_item_rejects_empty_item_id() -> None:
    with pytest.raises(ValidationError):
        TransactionReviewItem(
            item_id="",
            modelo=None,
            severity=ReviewSeverity.NORMAL,
            summary=_summary("tx"),
            drill_command="aeat financial txs classify t-1 --as ...",
            since=datetime(2026, 4, 10, tzinfo=UTC),
            source=_transaction(),
        )


def test_review_item_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TransactionReviewItem.model_validate(
            {
                "item_id": "t-1",
                "modelo": None,
                "severity": "normal",
                "summary": _summary("tx"),
                "drill_command": "aeat financial txs classify t-1 --as ...",
                "since": "2026-04-10T00:00:00+00:00",
                "source": _transaction().model_dump(mode="python"),
                "stray": "value",
            }
        )
