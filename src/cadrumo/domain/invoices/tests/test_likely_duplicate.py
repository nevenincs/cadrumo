"""The stored invoice a document may already be, across each rule and boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

import pytest

from ...iva.schema import InvoiceKind
from ..duplicates import LikelyDuplicate, likely_duplicate_invoice
from ..models import Invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RECORDING: Final = (
    Path(__file__).resolve().parents[5] / "native/desktop/frontend/src/dev/fixtures/ledgerInvoiceDuplicate.json"
)


@dataclass(frozen=True)
class _Stored:
    """The facts the rule reads, so its cases need no full invoice around them."""

    invoice_id: str
    kind: InvoiceKind
    invoice_number: str
    counterparty_tax_id: str | None
    issued_at: date
    grand_total: Decimal


def _stored(entry: dict[str, str]) -> Invoice:
    return cast(
        Invoice,
        _Stored(
            invoice_id=entry["invoice_id"],
            kind=InvoiceKind(entry["kind"]),
            invoice_number=entry["invoice_number"],
            counterparty_tax_id=entry["counterparty_tax_id"] or None,
            issued_at=date.fromisoformat(entry["issued_at"]),
            grand_total=Decimal(entry["grand_total"]),
        ),
    )


_RECORDED: Final = json.loads(_RECORDING.read_text(encoding="utf-8"))


@pytest.mark.parametrize("entry", _RECORDED["answers"], ids=lambda entry: entry["name"])
def test_every_recorded_answer_is_the_rules(entry: dict[str, object]) -> None:
    question = cast(dict[str, str | None], entry["question"])
    answer = cast(dict[str, str | None], entry["answer"])
    found = likely_duplicate_invoice(
        (_stored(stored) for stored in _RECORDED["invoices"]),
        kind=InvoiceKind(question["kind"]),
        invoice_number=question["invoice_number"],
        counterparty_tax_id=question["counterparty_tax_id"],
        invoice_date=date.fromisoformat(question["invoice_date"]) if question["invoice_date"] else None,
        grand_total=Decimal(question["grand_total"]) if question["grand_total"] else None,
    )

    assert (found.invoice_id if found else None, found.basis if found else None) == (
        answer["invoice_id"],
        answer["basis"],
    )


def test_the_same_total_written_differently_is_the_same_total() -> None:
    stored = _stored(
        {
            "invoice_id": "a",
            "kind": "received",
            "invoice_number": "X-1",
            "counterparty_tax_id": "B12345674",
            "issued_at": "2026-02-01",
            "grand_total": "121.00",
        }
    )
    found = likely_duplicate_invoice(
        (stored,),
        kind=InvoiceKind.RECEIVED,
        invoice_number="OTHER",
        counterparty_tax_id="b-12345674",
        invoice_date=date(2026, 2, 1),
        grand_total=Decimal("121"),
    )
    assert found == LikelyDuplicate(invoice_id="a", basis="party_day_total")
