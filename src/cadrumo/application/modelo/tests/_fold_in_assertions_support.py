"""Shared assertions for cross-period fold-in live tests."""

from __future__ import annotations

from decimal import Decimal


def _assert_distinct_positive(values: dict[str, Decimal]) -> Decimal:
    """Return the sum of ``values`` after asserting they are distinct and positive.

    Distinct non-equal positive values make the downstream fold assertion
    non-tautological: a silent blank (0), a single-quarter copy, or an
    off-by-quarter wiring cannot reproduce the strictly-positive sum of four
    distinct quarters.
    """
    assert len(set(values.values())) == len(values), f"seeded quarters must be distinct; got {values}"
    total = sum(values.values(), Decimal("0"))
    assert total > Decimal("0")
    return total
