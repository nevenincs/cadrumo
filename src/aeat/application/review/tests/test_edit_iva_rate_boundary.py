"""Tests for the V-3 review-edit boundary tightening.

Confirms that ``--set iva.rate=NN`` rejects values outside the
substrate-known IVA slot percentages (``0`` / ``4`` / ``10`` /
``21``) and that ``--set retention.rate=NN`` is bounded to ``[0,
100]``. The audit's V-3 finding warned that arbitrary Decimal
rates could leak into ledger records via the review-edit boundary;
this test suite is the regression guard.

The tests assert parser behavior at the public spec boundary: accepted
rates round-trip, unsupported rates fail before they can reach an
invoice review record, and retention rates stay in the legal percentage
envelope.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._edit import InvoiceEditSpec
from .._errors import EditParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("value", ["0", "4", "10", "21"])
def test_invoice_edit_iva_rate_accepts_canonical_substrate_slots(value: str) -> None:
    spec = InvoiceEditSpec.from_strings([f"iva.rate={value}"])
    assert spec.iva_rate == Decimal(value)


@pytest.mark.parametrize("bad_value", ["5", "7", "12", "15", "16", "21.5", "100"])
def test_invoice_edit_iva_rate_rejects_non_canonical_values(bad_value: str) -> None:
    with pytest.raises(EditParseError, match=r"unsupported-iva-rate") as excinfo:
        InvoiceEditSpec.from_strings([f"iva.rate={bad_value}"])
    assert "unsupported-iva-rate" in str(excinfo.value.reason)


def test_invoice_edit_iva_rate_rejects_negative_decimal() -> None:
    with pytest.raises(EditParseError, match=r"iva|rate|invalid"):
        InvoiceEditSpec.from_strings(["iva.rate=-21"])


def test_invoice_edit_iva_rate_rejects_garbage_string() -> None:
    with pytest.raises(EditParseError, match=r"iva|rate|invalid"):
        InvoiceEditSpec.from_strings(["iva.rate=twenty-one"])


@pytest.mark.parametrize("value", ["0", "7", "15", "19", "47", "100"])
def test_invoice_edit_retention_rate_accepts_values_in_range(value: str) -> None:
    spec = InvoiceEditSpec.from_strings([f"retention.rate={value}"])
    assert spec.retention_rate == Decimal(value)


@pytest.mark.parametrize("bad_value", ["-1", "101", "150", "1000"])
def test_invoice_edit_retention_rate_rejects_out_of_range_values(bad_value: str) -> None:
    with pytest.raises(EditParseError, match=r"retention-rate-out-of-range") as excinfo:
        InvoiceEditSpec.from_strings([f"retention.rate={bad_value}"])
    assert "retention-rate-out-of-range" in str(excinfo.value.reason)


def test_invoice_edit_with_canonical_iva_and_retention_round_trips() -> None:
    spec = InvoiceEditSpec.from_strings(["base=100.00", "iva.rate=21", "iva.amount=21.00", "retention.rate=15"])
    assert spec.base == Decimal("100.00")
    assert spec.iva_rate == Decimal("21")
    assert spec.iva_amount == Decimal("21.00")
    assert spec.retention_rate == Decimal("15")
