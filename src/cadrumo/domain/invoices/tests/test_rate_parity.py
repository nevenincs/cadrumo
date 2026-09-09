"""Authority-backed persisted IVA rate-slot tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...iva.errors import IvaRateNotFoundError
from ..enums import IvaRate, iva_rate_percentage, resolve_iva_rate_slot, resolve_iva_rate_slot_fact

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("slot", "on_date", "expected"),
    (
        (IvaRate.RATE_0, date(2026, 6, 1), Decimal("0")),
        (IvaRate.RATE_4, date(2026, 6, 1), Decimal("0.04")),
        (IvaRate.RATE_10, date(2026, 6, 1), Decimal("0.10")),
        (IvaRate.RATE_21, date(2026, 6, 1), Decimal("0.21")),
        (IvaRate.RATE_5, date(2024, 8, 15), Decimal("0.05")),
        (IvaRate.RATE_2, date(2024, 11, 15), Decimal("0.02")),
        (IvaRate.RATE_7_5, date(2024, 11, 15), Decimal("0.075")),
    ),
)
def test_persisted_numeric_slots_resolve_at_explicit_devengo_dates(
    slot: IvaRate,
    on_date: date,
    expected: Decimal,
) -> None:
    assert iva_rate_percentage(slot, on_date) == expected
    assert resolve_iva_rate_slot(expected * Decimal("100"), on_date) is slot


def test_coexisting_slot_resolution_retains_fact_provenance() -> None:
    resolved = resolve_iva_rate_slot_fact(IvaRate.RATE_2, date(2024, 11, 15))

    assert resolved is not None
    assert resolved.fact_id == "iva-rate-schedule"
    assert resolved.effective_date == date(2024, 11, 15)
    assert {selector.name: selector.value for selector in resolved.matched_selectors}["rate_role"] == "coexisting-2"
    assert resolved.legal_refs
    assert len(resolved.authority_digest) == 64


def test_transitional_slot_fails_closed_outside_its_window() -> None:
    with pytest.raises(IvaRateNotFoundError, match=r"errors\.iva\.rate_slot_not_in_force"):
        iva_rate_percentage(IvaRate.RATE_2, date(2025, 6, 1))


def test_nonnumeric_tokens_remain_nonnumeric() -> None:
    on_date = date(2026, 6, 1)
    assert iva_rate_percentage(IvaRate.EXEMPT, on_date) is None
    assert iva_rate_percentage(IvaRate.NOT_SUBJECT, on_date) is None
