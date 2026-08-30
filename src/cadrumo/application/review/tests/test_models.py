"""Pydantic shape + invariant tests for the review-queue models."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.severity import BaseSeverity
from ....core.i18n import Translatable as tr
from ....domain.filing.schema import ModeloValidationFinding
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..enums import ReviewItemKind, ReviewSeverity
from ..models import FindingReviewItem, InvoiceReviewItem, ReviewItem, TransactionReviewItem

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_REVIEW_ITEM_ADAPTER: TypeAdapter[ReviewItem] = TypeAdapter(ReviewItem)
_REVIEW_FINDING_CASILLA: CasillaId = validated_casilla_id("03", surface="_REVIEW_FINDING_CASILLA")


def _summary(text: str = "demo") -> tr:
    return tr("translation")


def _raw() -> RawTransaction:
    return RawTransaction(
        provider_transaction_id="prov-1",
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
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        },
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
        },
    )


def _finding() -> ModeloValidationFinding:
    return ModeloValidationFinding(
        casilla_id=_REVIEW_FINDING_CASILLA,
        severity=BaseSeverity.ERROR,
        code="casilla-out-of-range",
        message=_summary("range error"),
    )


def test_transaction_review_item_round_trips_through_json() -> None:
    item = TransactionReviewItem(
        item_id="t-1",
        modelo=None,
        severity=ReviewSeverity.NORMAL,
        summary=_summary("tx"),
        drill_command="aeat app ledger review t-1",
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
            drill_command="aeat app ledger review t-1",
            since=datetime(2026, 4, 10, tzinfo=UTC),
            source=_transaction(),
        ),
        InvoiceReviewItem(
            item_id="i-1",
            modelo=None,
            severity=ReviewSeverity.HIGH,
            summary=_summary("inv"),
            drill_command="aeat app review view i-1",
            since=datetime(2026, 4, 1, tzinfo=UTC),
            source=_invoice(),
        ),
        FindingReviewItem(
            item_id="f-1",
            modelo="130",
            severity=ReviewSeverity.CRITICAL,
            summary=_summary("finding"),
            drill_command="aeat app review view draft-1:casilla-out-of-range:03",
            since=datetime(2026, 4, 14, tzinfo=UTC),
            source=_finding(),
            draft_id="draft-1",
            draft_path="draft.json",
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
        drill_command="aeat app review view draft-1:_status:VALIDATED",
        since=datetime(2026, 4, 14, tzinfo=UTC),
        source=None,
        draft_id="draft-1",
        draft_path="draft.json",
    )
    restored = FindingReviewItem.model_validate_json(placeholder.model_dump_json())
    assert restored.source is None


def test_review_item_rejects_naive_since_timestamp() -> None:
    with pytest.raises(ValidationError, match=r"since|timezone|tz-aware"):
        TransactionReviewItem(
            item_id="t-1",
            modelo=None,
            severity=ReviewSeverity.NORMAL,
            summary=_summary("tx"),
            drill_command="aeat app ledger review t-1",
            since=datetime(2026, 4, 10),
            source=_transaction(),
        )


def test_review_item_rejects_empty_item_id() -> None:
    with pytest.raises(ValidationError, match=r"item_id|at least 1 character"):
        TransactionReviewItem(
            item_id="",
            modelo=None,
            severity=ReviewSeverity.NORMAL,
            summary=_summary("tx"),
            drill_command="aeat app ledger review t-1",
            since=datetime(2026, 4, 10, tzinfo=UTC),
            source=_transaction(),
        )


def test_review_item_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        TransactionReviewItem.model_validate(
            {
                "item_id": "t-1",
                "modelo": None,
                "severity": "normal",
                "summary": _summary("tx"),
                "drill_command": "aeat app ledger review t-1",
                "since": "2026-04-10T00:00:00+00:00",
                "source": _transaction().model_dump(mode="python"),
                "stray": "value",
            },
        )
