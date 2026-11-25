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

_QUESTIONS: Final = (
    Path(__file__).resolve().parents[5] / "dev/fixtures/ledger-recording-questions/ledgerInvoiceDuplicate.json"
)
_ASKED: Final = json.loads(_QUESTIONS.read_text(encoding="utf-8"))

#: What each committed question must answer, worked from the rules: a stated number matches under the same
#: tax id, or under none stated, in the same direction; without a number the party, day and total must all
#: agree, and nothing stated matches nothing.
_EXPECTED: Final[dict[str, tuple[str | None, str | None]]] = {
    "the number comes first": ("b-same-number", "number"),
    "the party, day and total where no number matches": (None, None),
    "a number under a disagreeing tax id is not one": (None, None),
    "a number with no stated tax id is one": ("b-same-number", "number"),
    "the other direction is not one": (None, None),
    "another day is not one": (None, None),
    "no stated total is not one": (None, None),
    "nothing stated is not one": (None, None),
}


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def test_the_committed_questions_are_the_ones_the_expectations_state() -> None:
    assert sorted(entry["name"] for entry in _ASKED["answers"]) == sorted(_EXPECTED)


@pytest.mark.parametrize("entry", _ASKED["answers"], ids=lambda entry: entry["name"])
def test_every_committed_question_is_answered_as_the_rules_say(entry: dict[str, object]) -> None:
    question = cast(dict[str, str | None], entry["question"])
    invoice_id, basis = _EXPECTED[cast(str, entry["name"])]

    assert recorded_duplicate_answer(_ASKED["invoices"], question) == {"invoice_id": invoice_id, "basis": basis}


def test_the_same_total_written_differently_is_the_same_total() -> None:
    stored = stored_invoice(
        {
            "invoice_id": "a",
            "kind": "received",
            "invoice_number": "X-1",
            "counterparty_tax_id": "B00015016",
            "issued_at": "2026-02-01",
            "grand_total": "121.00",
        }
    )
    found = likely_duplicate_invoice(
        (stored,),
        kind=InvoiceKind.RECEIVED,
        invoice_number="OTHER",
        counterparty_tax_id="b-00015016",
        invoice_date=date(2026, 2, 1),
        grand_total=Decimal("121"),
    )
    assert found == LikelyDuplicate(invoice_id=stored.invoice_id, basis="party_day_total")
