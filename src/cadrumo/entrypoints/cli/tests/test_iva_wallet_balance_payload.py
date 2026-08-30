"""The IVA wallet balance payload refuses what the canonical report refuses.

:class:`~domain.iva_compensation.IvaWalletBalanceReport` constrains its
reference year, its non-negative Decimal balances, its lot count and its
bounded next-expiry year. The CLI
:class:`~entrypoints.cli._modelo_iva_wallet_payloads.IvaWalletBalanceResult`
redeclared every amount as a free string and every year/count as an unbounded
primitive, so a balance claim the domain rejects could still be emitted at the
operator-facing boundary -- the one surface a reader cannot check against the
domain.

Each case below is mutated from a value the canonical report rejects, and the
parity test asserts the two agree rather than asserting each in isolation, so
a future edit that re-loosens the payload fails here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.iva_compensation.balance import IvaWalletBalanceReport
from .._modelo_iva_wallet_payloads import IvaWalletBalanceResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _report(**overrides: Any) -> IvaWalletBalanceReport:
    base: dict[str, Any] = {
        "as_of_year": 2026,
        "total_balance": Decimal("100.00"),
        "active_balance": Decimal("60.00"),
        "expired_balance": Decimal("40.00"),
        "lot_count": 2,
        "next_expiry_year": 2029,
        "unallocated_applied_amount": Decimal("0.00"),
    }
    base.update(overrides)
    return IvaWalletBalanceReport(**base)  # type: ignore[arg-type]


def _payload(**overrides: Any) -> IvaWalletBalanceResult:
    base: dict[str, Any] = {
        "as_of_year": 2026,
        "total_balance": "100.00",
        "active_balance": "60.00",
        "expired_balance": "40.00",
        "lot_count": 2,
        "next_expiry_year": 2029,
        "unallocated_applied_amount": "0.00",
    }
    base.update(overrides)
    return IvaWalletBalanceResult.model_validate(base)


def test_a_valid_report_projects_onto_the_payload() -> None:
    """Positive control: the canonical shape must still round-trip to the wire."""
    report = _report()
    payload = IvaWalletBalanceResult(
        as_of_year=report.as_of_year,
        total_balance=str(report.total_balance),
        active_balance=str(report.active_balance),
        expired_balance=str(report.expired_balance),
        lot_count=report.lot_count,
        next_expiry_year=report.next_expiry_year,
        unallocated_applied_amount=str(report.unallocated_applied_amount),
    )

    assert payload.as_of_year == 2026
    assert payload.total_balance == "100.00"
    assert payload.next_expiry_year == 2029
    assert payload.model_dump(mode="json")["lot_count"] == 2


@pytest.mark.parametrize(
    "field",
    ["total_balance", "active_balance", "expired_balance", "unallocated_applied_amount"],
)
@pytest.mark.parametrize("malformed", ["-1.00", "NaN", "Infinity", "-0.01", "not-a-number", ""])
def test_payload_refuses_an_amount_the_report_could_not_produce(field: str, malformed: str) -> None:
    with pytest.raises(ValidationError):
        _payload(**{field: malformed})


@pytest.mark.parametrize("bad_year", [1900, 0, 2100, -1])
def test_payload_refuses_a_reference_year_outside_the_canonical_window(bad_year: int) -> None:
    with pytest.raises(ValidationError):
        _payload(as_of_year=bad_year)
    with pytest.raises(ValidationError):
        _report(as_of_year=bad_year)


@pytest.mark.parametrize("bad_count", [-1, -99])
def test_payload_refuses_a_negative_lot_count(bad_count: int) -> None:
    with pytest.raises(ValidationError):
        _payload(lot_count=bad_count)
    with pytest.raises(ValidationError):
        _report(lot_count=bad_count)


@pytest.mark.parametrize("bad_expiry", [1999, 2201])
def test_payload_refuses_an_out_of_range_next_expiry_year(bad_expiry: int) -> None:
    with pytest.raises(ValidationError):
        _payload(next_expiry_year=bad_expiry)
    with pytest.raises(ValidationError):
        _report(next_expiry_year=bad_expiry)


def test_payload_keeps_the_absent_next_expiry_case() -> None:
    """``None`` is the canonical 'no lot expires yet' state, not a gap."""
    assert _payload(next_expiry_year=None).next_expiry_year is None
    assert _report(next_expiry_year=None).next_expiry_year is None
