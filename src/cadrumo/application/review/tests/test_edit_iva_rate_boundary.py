"""Tests for the V-3 review-edit boundary tightening.

Confirms that ``--set iva.rate=NN`` rejects values outside the
substrate-known IVA slot percentages and that ``--set retention.rate=NN``
is bounded to ``[0, 100]``. The audit's V-3 finding warned that arbitrary
Decimal rates could leak into ledger records via the review-edit boundary;
this test suite is the regression guard.

The accepted set is read from
:func:`~cadrumo.domain.invoices.numeric_iva_rate_percentages`, never listed
here. It was listed once, as ``0 / 4 / 10 / 21`` with ``5`` named among the
rejects, and the RD-ley 4/2024 food slots made that list wrong in both
directions at once: the parser correctly began accepting 5 % while this test
still demanded a refusal. A boundary test that hardcodes the boundary stops
testing the parser and starts testing a copy of it.

The tests assert parser behavior at the public spec boundary: accepted
rates round-trip, unsupported rates fail before they can reach an
invoice review record, and retention rates stay in the legal percentage
envelope.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.invoices.enums import numeric_iva_rate_percentages
from .._edit import InvoiceEditSpec
from ..errors import EditParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACCEPTED_RATES = tuple(sorted(numeric_iva_rate_percentages()))
"""Every percentage an IvaRate slot names, read from the taxonomy itself."""

_REJECTED_RATES = tuple(
    candidate
    for candidate in (Decimal("3"), Decimal("7"), Decimal("12"), Decimal("15"), Decimal("16"), Decimal("100"))
    if candidate not in numeric_iva_rate_percentages()
)
"""Plausible-looking percentages no Spanish IVA slot names.

Filtered against the live taxonomy rather than asserted absent, so a future
statute that turns one of these into a real slot drops it from the reject list
instead of failing a test for doing the right thing.
"""


@pytest.mark.parametrize("value", _ACCEPTED_RATES)
def test_invoice_edit_iva_rate_accepts_canonical_substrate_slots(value: Decimal) -> None:
    spec = InvoiceEditSpec.from_strings([f"iva.rate={value}"])
    assert spec.iva_rate == value


def test_accepted_rate_set_is_not_empty_and_covers_the_standing_tiers() -> None:
    """Guard the derivation: an empty or collapsed accepted set would make the acceptance test vacuous.

    Parametrizing over a function's own output means an accidental empty
    return would silently reduce the acceptance test to zero cases and still
    report green. The four standing LIVA rates must always be in there.
    """
    assert {Decimal("0"), Decimal("4"), Decimal("10"), Decimal("21")} <= set(_ACCEPTED_RATES)
    assert _REJECTED_RATES, "the reject list filtered itself empty; pick percentages outside the taxonomy"


@pytest.mark.parametrize("bad_value", (*_REJECTED_RATES, Decimal("21.5")))
def test_invoice_edit_iva_rate_rejects_non_canonical_values(bad_value: Decimal) -> None:
    with pytest.raises(EditParseError) as excinfo:
        InvoiceEditSpec.from_strings([f"iva.rate={bad_value}"])
    assert "unsupported-iva-rate" in str(excinfo.value.reason)


def test_invoice_edit_iva_rate_rejects_negative_decimal() -> None:
    with pytest.raises(EditParseError):
        InvoiceEditSpec.from_strings(["iva.rate=-21"])


def test_invoice_edit_iva_rate_rejects_garbage_string() -> None:
    with pytest.raises(EditParseError):
        InvoiceEditSpec.from_strings(["iva.rate=twenty-one"])


@pytest.mark.parametrize("value", ("0", "7", "15", "19", "47", "100"))
def test_invoice_edit_retention_rate_accepts_values_in_range(value: str) -> None:
    spec = InvoiceEditSpec.from_strings([f"retention.rate={value}"])
    assert spec.retention_rate == Decimal(value)


@pytest.mark.parametrize("bad_value", ("-1", "101", "150", "1000"))
def test_invoice_edit_retention_rate_rejects_out_of_range_values(bad_value: str) -> None:
    with pytest.raises(EditParseError) as excinfo:
        InvoiceEditSpec.from_strings([f"retention.rate={bad_value}"])
    assert "retention-rate-out-of-range" in str(excinfo.value.reason)


def test_invoice_edit_with_canonical_iva_and_retention_round_trips() -> None:
    spec = InvoiceEditSpec.from_strings(["base=100.00", "iva.rate=21", "iva.amount=21.00", "retention.rate=15"])
    assert spec.base == Decimal("100.00")
    assert spec.iva_rate == Decimal("21")
    assert spec.iva_amount == Decimal("21.00")
    assert spec.retention_rate == Decimal("15")
