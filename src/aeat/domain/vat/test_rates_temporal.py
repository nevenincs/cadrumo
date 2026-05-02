"""Period-versioned VAT rate lookup tests.

Confirms that :func:`aeat.domain.vat.lookup_rate` resolves the correct
:class:`aeat.domain.vat.VATRate` record across the 2024 / 2025 ES window
boundary, and that the load-time non-overlap invariant in
:func:`aeat.domain.vat._rates._assert_no_overlap` rejects clashing windows.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from . import EUMemberState, VATRateKind, lookup_rate
from ._rates import _assert_no_overlap
from ._schema import VATRate
from .errors import VatRateNotFoundError, VatRateOverlapError

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_es_general_2024_rate() -> None:
    rate = lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2024, 6, 15))
    assert rate.pct == Decimal("21")
    assert rate.effective_from == date(2024, 1, 1)
    assert rate.effective_until == date(2024, 12, 31)


def test_es_general_2025_rate() -> None:
    rate = lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2025, 6, 15))
    assert rate.pct == Decimal("21")
    assert rate.effective_from == date(2025, 1, 1)
    assert rate.effective_until is None


def test_es_general_2024_last_day() -> None:
    """December 31 2024 still resolves to the 2024 record."""
    rate = lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2024, 12, 31))
    assert rate.effective_until == date(2024, 12, 31)


def test_es_general_2025_first_day() -> None:
    """January 1 2025 resolves to the 2025 record (no overlap)."""
    rate = lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2025, 1, 1))
    assert rate.effective_from == date(2025, 1, 1)


def test_es_super_reduced_2024_and_2025_both_resolve() -> None:
    """The 4 % super-reducido is registered for both years."""
    rate_2024 = lookup_rate(EUMemberState.ES, VATRateKind.SUPER_REDUCED, date(2024, 6, 15))
    rate_2025 = lookup_rate(EUMemberState.ES, VATRateKind.SUPER_REDUCED, date(2025, 6, 15))
    assert rate_2024.pct == Decimal("4")
    assert rate_2025.pct == Decimal("4")


def test_es_reduced_2024_and_2025_both_resolve() -> None:
    """The 10 % reducido is registered for both years."""
    rate_2024 = lookup_rate(EUMemberState.ES, VATRateKind.REDUCED, date(2024, 6, 15))
    rate_2025 = lookup_rate(EUMemberState.ES, VATRateKind.REDUCED, date(2025, 6, 15))
    assert rate_2024.pct == Decimal("10")
    assert rate_2025.pct == Decimal("10")


def test_es_pre_2024_lookup_raises() -> None:
    """Dates before the 2024 baseline have no registered rate."""
    with pytest.raises(VatRateNotFoundError):
        lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, date(2023, 6, 1))


def test_overlap_invariant_rejects_clashing_windows() -> None:
    """Synthetic overlapping windows must raise :class:`VatRateOverlapError`."""
    overlapping = (
        VATRate(
            member_state=EUMemberState.DE,
            kind=VATRateKind.GENERAL,
            pct=Decimal("19"),
            effective_from=date(2024, 1, 1),
            effective_until=date(2024, 12, 31),
            boe_or_directive_reference="synthetic A",
        ),
        VATRate(
            member_state=EUMemberState.DE,
            kind=VATRateKind.GENERAL,
            pct=Decimal("19"),
            effective_from=date(2024, 6, 1),  # overlaps the first window
            effective_until=None,
            boe_or_directive_reference="synthetic B",
        ),
    )
    with pytest.raises(VatRateOverlapError, match="overlapping windows"):
        _assert_no_overlap(EUMemberState.DE, overlapping)


def test_overlap_invariant_accepts_disjoint_windows() -> None:
    """Disjoint windows are accepted without error."""
    disjoint = (
        VATRate(
            member_state=EUMemberState.DE,
            kind=VATRateKind.GENERAL,
            pct=Decimal("19"),
            effective_from=date(2024, 1, 1),
            effective_until=date(2024, 12, 31),
            boe_or_directive_reference="synthetic A",
        ),
        VATRate(
            member_state=EUMemberState.DE,
            kind=VATRateKind.GENERAL,
            pct=Decimal("19"),
            effective_from=date(2025, 1, 1),
            effective_until=None,
            boe_or_directive_reference="synthetic B",
        ),
    )
    _assert_no_overlap(EUMemberState.DE, disjoint)
