"""The stored invoice a document may already be, across each rule and boundary."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

import pytest

from ...calculations.registry.authority import bundled_indexed_authority
from ...iva.schema import InvoiceKind
from ..duplicates import LikelyDuplicate, likely_duplicate_invoice
from .duplicate_recording_support import recorded_duplicate_answer, stored_invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RECORDING: Final = (
    Path(__file__).resolve().parents[5] / "native/desktop/frontend/src/dev/fixtures/ledgerInvoiceDuplicate.json"
)


_RECORDED: Final = json.loads(_RECORDING.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


@pytest.mark.parametrize("entry", _RECORDED["answers"], ids=lambda entry: entry["name"])
def test_every_recorded_answer_is_the_rules(entry: dict[str, object]) -> None:
    question = cast(dict[str, str | None], entry["question"])

    assert recorded_duplicate_answer(_RECORDED["invoices"], question) == entry["answer"]


def test_the_same_total_written_differently_is_the_same_total() -> None:
    stored = stored_invoice(
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
    assert found == LikelyDuplicate(invoice_id=stored.invoice_id, basis="party_day_total")
