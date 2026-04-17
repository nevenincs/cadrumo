"""Unit tests for :mod:`aeat.financial.vat._rates`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from . import (
    VAT_RATE_TABLE,
    EUMemberState,
    VATRateKind,
    VatRateNotFoundError,
    lookup_rate,
)


@pytest.mark.unit
def test_rate_table_covers_all_27_member_states() -> None:
    """The rate table carries an entry for every EUMemberState."""
    assert set(VAT_RATE_TABLE.keys()) == set(EUMemberState)


@pytest.mark.unit
def test_rate_table_has_at_least_50_entries() -> None:
    """Aggregate rate count must meet the ≥50 acceptance threshold."""
    total = sum(len(rates) for rates in VAT_RATE_TABLE.values())
    assert total >= 50


@pytest.mark.unit
def test_es_rate_table_fully_expanded() -> None:
    """Spain must expose general / reduced / super_reduced / zero tiers."""
    es_kinds = {rate.kind for rate in VAT_RATE_TABLE[EUMemberState.ES]}
    assert {
        VATRateKind.GENERAL,
        VATRateKind.REDUCED,
        VATRateKind.SUPER_REDUCED,
        VATRateKind.ZERO,
    } <= es_kinds


@pytest.mark.unit
def test_lookup_rate_returns_spain_general_21() -> None:
    """`lookup_rate` resolves the Spanish general rate for mid-2025."""
    rate = lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2025, 6, 1))
    assert rate.pct == Decimal("21")


@pytest.mark.unit
def test_lookup_rate_raises_for_unknown_kind() -> None:
    """Denmark has no reduced rate; lookup must raise."""
    with pytest.raises(VatRateNotFoundError):
        lookup_rate(EUMemberState.DK, VATRateKind.REDUCED, date(2025, 6, 1))


@pytest.mark.unit
def test_lookup_rate_respects_effective_from() -> None:
    """Rates dated before `effective_from` must not match."""
    with pytest.raises(VatRateNotFoundError):
        lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2024, 12, 31))


@pytest.mark.unit
def test_every_rate_window_is_well_ordered() -> None:
    """Every VATRate with both bounds set must have from <= until."""
    for rates in VAT_RATE_TABLE.values():
        for rate in rates:
            if rate.effective_until is not None:
                assert rate.effective_from <= rate.effective_until
