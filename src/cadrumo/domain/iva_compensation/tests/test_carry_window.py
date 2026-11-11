"""The IVA compensation carry window resolves from the held published authority."""

from __future__ import annotations

from datetime import date

import pytest

from ...calculations.registry.authority import bundled_indexed_authority
from ..carry_window import resolve_iva_compensation_carry_window_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_carry_window_uses_the_published_fact_at_each_explicit_filing_date() -> None:
    """Each source cohort date resolves through one held operation and current published fact."""
    dates = (
        date(2024, 1, 1),
        date(2025, 1, 1),
        date(2028, 1, 1),
        date(2029, 1, 1),
    )

    with bundled_indexed_authority().operation() as operation:
        windows = tuple(
            resolve_iva_compensation_carry_window_years(effective_date=effective_date, operation=operation)
            for effective_date in dates
        )

    assert windows == (4, 4, 4, 4)
