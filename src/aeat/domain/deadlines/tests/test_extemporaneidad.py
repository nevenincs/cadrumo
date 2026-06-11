"""Tests for extemporaneidad detection and Art. 27 LGT recargo computation.

External authority: Ley 58/2003 (LGT) Art. 27.2, post-Ley 11/2021
amendment.  Surcharge escalation:

  - 1% per month for months 1-12 (fractions treated as full months
    by the bracket table; see ley-58-2003-recargo-bands.toml).
  - After 12 months: 15% plus intereses de demora.

The anti-tautology test is deliberately divorced from the registry
formula that would compute the same result: it drives the domain
``resolve_recargo_band`` function with a date arithmetic value
derived from Ley 58/2003 directly, not from the registry TOML.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import Period
from .._plazo import resolve_filing_closes_on
from .._recargo import build_recovery_for_overdue, load_recargo_bands, resolve_recargo_band

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# Anti-tautology: Art. 27.2 LGT 12-month overdue case
# ---------------------------------------------------------------------------


def test_after_12_months_overdue_yields_15_pct_plus_interest() -> None:
    """Plazo closed 2024-11-30; today 2026-05-27 → 543 days late → after_12_months band.

    External authority: Ley 58/2003 Art. 27.2 (post-Ley 11/2021).
    After 12 months (366+ days) the applicable recargo is 15% plus
    intereses de demora.  543 days = 17.8 months, clearly in the
    after_12_months bracket.

    This test does NOT re-derive the days-late value from the same
    formula the registry declares; it computes the days from the two
    calendar dates and asserts against the Ley 58/2003 statutory text.
    """
    plazo_closes_on = date(2024, 11, 30)
    reference_today = date(2026, 5, 27)
    days_late = (reference_today - plazo_closes_on).days
    # 543 days — independently: from Nov 30 2024 to May 27 2026 is 543 days.
    assert days_late == 543

    bands = load_recargo_bands()
    band = resolve_recargo_band(days_late, bands)

    assert band.id == "after_12_months"
    assert band.surcharge_pct == Decimal("15.00")
    assert band.interest_applies is True
    assert "ley-58-2003" in band.legal_ref


def test_after_12_months_recovery_payload() -> None:
    """build_recovery_for_overdue with 543 days produces a fully-populated Recovery."""
    recovery = build_recovery_for_overdue(days_late=543, modelo="303", period=Period.from_year_and_code(2024, "4T"))
    assert recovery.still_filable is True
    assert recovery.recargo_band.id == "after_12_months"
    assert recovery.recargo_band.interest_applies is True
    assert recovery.recargo_band.surcharge_pct == Decimal("15.00")
    assert recovery.next_command == "aeat app modelo work --help"


def test_within_30_days_no_interest() -> None:
    """15 days overdue → within_30_days band, 1% recargo, no interest.

    External authority: Ley 58/2003 Art. 27.2 post-Ley 11/2021,
    first bracket (1-30 days → 1%).
    """
    bands = load_recargo_bands()
    band = resolve_recargo_band(15, bands)
    assert band.id == "within_30_days"
    assert band.surcharge_pct == Decimal("1.00")
    assert band.interest_applies is False


def test_within_6_months_no_interest() -> None:
    """120 days overdue → within_6_months band, 6% recargo, no interest.

    120 days falls in the 91-180 day bracket (months 4-6) per
    Ley 58/2003 Art. 27.2.
    """
    bands = load_recargo_bands()
    band = resolve_recargo_band(120, bands)
    assert band.id == "within_6_months"
    assert band.surcharge_pct == Decimal("6.00")
    assert band.interest_applies is False


def test_within_12_months_no_interest() -> None:
    """300 days overdue (about 10 months) → within_12_months band, 12% recargo, no interest.

    300 days is within the 181-365 day bracket per Ley 58/2003 Art. 27.2.
    """
    bands = load_recargo_bands()
    band = resolve_recargo_band(300, bands)
    assert band.id == "within_12_months"
    assert band.surcharge_pct == Decimal("12.00")
    assert band.interest_applies is False


# ---------------------------------------------------------------------------
# resolve_filing_closes_on — registry integration
# ---------------------------------------------------------------------------


def test_resolve_filing_closes_on_m130_2026_q1_returns_date() -> None:
    """M130 Q1 2026 closes_on is registered and resolvable.

    M130 (pagos fraccionados IRPF estimación directa) has deadline
    windows for 2026 registered in the canonical TOML.  The resolver
    must return a non-None date for the Q1 window.
    """
    closes_on = resolve_filing_closes_on("130", 2026, Period.from_year_and_code(2026, "1T"))
    assert closes_on is not None
    assert isinstance(closes_on, date)
    # M130 Q1 2026: typically closes on 2026-04-20 (AEAT plazo trimestral).
    assert closes_on.year == 2026
    assert closes_on.month in (4, 5)  # April/May for Q1 plazo


def test_resolve_filing_closes_on_unknown_modelo_returns_none() -> None:
    """A modelo with no registry deadline windows returns None gracefully."""
    result = resolve_filing_closes_on("999", 2026, Period.from_year_and_code(2026, "1T"))
    assert result is None


def test_resolve_filing_closes_on_wrong_period_returns_none() -> None:
    """A period not registered for this modelo+year returns None."""
    result = resolve_filing_closes_on("130", 2026, Period.from_year_and_code(2026, "1P"))
    assert result is None


def test_resolve_filing_closes_on_annual_period() -> None:
    """M100 annual period '0A' resolves to a date in the correct year."""
    closes_on = resolve_filing_closes_on("100", 2024, Period.from_year_and_code(2024, "0A"))
    assert closes_on is not None
    # M100 2024 anual plazo: AEAT opens April, closes June 30 2025.
    assert closes_on.year == 2025
    assert closes_on.month == 6
