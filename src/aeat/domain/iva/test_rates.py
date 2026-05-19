"""Unit tests for the EU VAT rate table exposed by :mod:`aeat.domain.vat`.

Covers the 27-state coverage invariant, the Spanish multi-tier expansion, the
:func:`aeat.domain.vat.lookup_rate` happy and error paths, and the per-record
window well-orderedness invariant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from . import (
    EUMemberState,
    VATRateKind,
    VatRateNotFoundError,
    load_vat_rate_table,
    lookup_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_rate_table_covers_all_27_member_states() -> None:
    """The rate table carries an entry for every EUMemberState."""
    assert set(load_vat_rate_table().keys()) == set(EUMemberState)


def test_rate_table_has_at_least_50_entries() -> None:
    """Aggregate rate count must meet the at-least-50-entries acceptance threshold."""
    total = sum(len(rates) for rates in load_vat_rate_table().values())
    assert total >= 50


def test_es_rate_table_fully_expanded() -> None:
    """Spain must expose general / reduced / super_reduced / zero tiers."""
    es_kinds = {rate.kind for rate in load_vat_rate_table()[EUMemberState.ES]}
    assert {
        VATRateKind.GENERAL,
        VATRateKind.REDUCED,
        VATRateKind.SUPER_REDUCED,
        VATRateKind.ZERO,
    } <= es_kinds


def test_lookup_rate_returns_spain_general_21() -> None:
    """`lookup_rate` resolves the Spanish general rate for mid-2025."""
    rate = lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2025, 6, 1))
    assert rate.pct == Decimal("21")


def test_lookup_rate_raises_for_unknown_kind() -> None:
    """Denmark has no reduced rate; lookup must raise."""
    with pytest.raises(VatRateNotFoundError, match=r"DK|REDUCED|rate"):
        lookup_rate(EUMemberState.DK, VATRateKind.REDUCED, date(2025, 6, 1))


def test_lookup_rate_respects_effective_from() -> None:
    """Rates dated before the earliest registered window must not match.

    The 2024 baseline ES window means ``2024-12-31`` resolves successfully;
    the pre-2024 range still has no registered record and must raise.
    """
    with pytest.raises(VatRateNotFoundError, match=r"ES|GENERAL|2023|rate"):
        lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2023, 12, 31))


def test_every_rate_window_is_well_ordered() -> None:
    """Every :class:`VATRate` with both bounds set must satisfy ``effective_from <= effective_until``."""
    for rates in load_vat_rate_table().values():
        for rate in rates:
            if rate.effective_until is not None:
                assert rate.effective_from <= rate.effective_until
