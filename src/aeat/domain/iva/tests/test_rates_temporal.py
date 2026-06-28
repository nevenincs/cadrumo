"""Period-versioned IVA rate lookup tests.

Confirms that :func:`aeat.domain.iva.lookup_rate` resolves the correct
:class:`aeat.domain.iva.IvaRateRecord` record across the 2024 / 2025 ES window
boundary, and that the committed registry has no overlapping effective
windows.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest

from .. import EUMemberState, IvaRateKind, load_iva_rate_table, lookup_rate
from .._errors import IvaRateNotFoundError, IvaRateOverlapError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_es_general_2024_rate() -> None:
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2024, 6, 15))
    assert rate.pct == Decimal("21")
    assert rate.effective_from == date(2024, 1, 1)
    assert rate.effective_until == date(2024, 12, 31)


def test_es_general_2025_rate() -> None:
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2025, 6, 15))
    assert rate.pct == Decimal("21")
    assert rate.effective_from == date(2025, 1, 1)
    assert rate.effective_until is None


def test_es_general_2024_last_day() -> None:
    """December 31 2024 still resolves to the 2024 record."""
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2024, 12, 31))
    assert rate.effective_until == date(2024, 12, 31)


def test_es_general_2025_first_day() -> None:
    """January 1 2025 resolves to the 2025 record (no overlap)."""
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2025, 1, 1))
    assert rate.effective_from == date(2025, 1, 1)


def test_es_super_reduced_2024_and_2025_both_resolve() -> None:
    """The 4 % super-reducido is registered for both years."""
    rate_2024 = lookup_rate(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, date(2024, 6, 15))
    rate_2025 = lookup_rate(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, date(2025, 6, 15))
    assert rate_2024.pct == Decimal("4")
    assert rate_2025.pct == Decimal("4")


def test_es_reduced_2024_and_2025_both_resolve() -> None:
    """The 10 % reducido is registered for both years."""
    rate_2024 = lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, date(2024, 6, 15))
    rate_2025 = lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, date(2025, 6, 15))
    assert rate_2024.pct == Decimal("10")
    assert rate_2025.pct == Decimal("10")


def test_es_pre_2024_lookup_raises() -> None:
    """Dates before the 2024 baseline have no registered rate."""
    with pytest.raises(IvaRateNotFoundError, match=r"ES|GENERAL|2023|rate"):
        lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2023, 6, 1))


def test_committed_registry_has_no_overlapping_windows() -> None:
    for member_state, rates in load_iva_rate_table().items():
        by_kind: dict[IvaRateKind, list[tuple[date, date]]] = {}
        for rate in rates:
            by_kind.setdefault(rate.kind, []).append((rate.effective_from, rate.effective_until or date.max))
        for kind, windows in by_kind.items():
            ordered = sorted(windows)
            for previous, current in pairwise(ordered):
                if previous[1] >= current[0]:
                    raise IvaRateOverlapError(f"{member_state.value}/{kind.value}: {previous} overlaps {current}")
