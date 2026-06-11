"""Tests for the Ley 58/2003 art-27 recargo bracket loader and resolver."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from .._errors import DeadlineValidationError
from .._recargo import build_recovery_for_overdue, load_recargo_bands, resolve_recargo_band

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_recargo_bands_load_from_registry_toml_in_order() -> None:
    """The bracket TOML must materialise into bands sorted by min_days_late.

    External authority: ley-58-2003:art-27 (Ley General Tributaria,
    post-Ley 11/2021). Bands are grouped windows of the per-month
    escalation; the canonical TOML lives at
    ``registry/aeat/legal/ley-58-2003-recargo-bands.toml``.
    """
    bands = load_recargo_bands()
    assert len(bands) >= 4
    # Sorted ascending by lower bound.
    prior = 0
    for band in bands:
        assert band.min_days_late > prior
        prior = band.min_days_late
    # Every band carries the Ley 58/2003 reference.
    assert all("ley-58-2003" in band.legal_ref for band in bands)
    # Exactly one band has interest_applies=True (the after-12-months tail).
    interest_bands = [b for b in bands if b.interest_applies]
    assert len(interest_bands) == 1
    assert interest_bands[0].max_days_late is None


def test_overdue_5_days_returns_within_30_days_band() -> None:
    """5 days late falls in the first band (<=30 days)."""
    bands = load_recargo_bands()
    band = resolve_recargo_band(5, bands)
    assert band.id == "within_30_days"
    assert band.surcharge_pct == Decimal("1.00")
    assert band.interest_applies is False


def test_overdue_60_days_returns_within_3_months_band() -> None:
    """60 days late falls in the 31-90 day band."""
    bands = load_recargo_bands()
    band = resolve_recargo_band(60, bands)
    assert band.id == "within_3_months"
    assert band.surcharge_pct == Decimal("3.00")
    assert band.interest_applies is False


def test_overdue_5_months_returns_within_6_months_band() -> None:
    """~150 days late (5 months) falls in the 91-180 day band."""
    bands = load_recargo_bands()
    band = resolve_recargo_band(150, bands)
    assert band.id == "within_6_months"
    assert band.surcharge_pct == Decimal("6.00")
    assert band.interest_applies is False


def test_overdue_13_months_adds_interest() -> None:
    """Beyond 12 months the 15% + interest band applies."""
    bands = load_recargo_bands()
    band = resolve_recargo_band(400, bands)
    assert band.id == "after_12_months"
    assert band.surcharge_pct == Decimal("15.00")
    assert band.interest_applies is True


def test_resolve_recargo_band_rejects_zero_days_late() -> None:
    bands = load_recargo_bands()
    with pytest.raises(ValueError, match="days_late must be >= 1"):
        resolve_recargo_band(0, bands)


def test_build_recovery_carries_runnable_next_command() -> None:
    """Recovery's next_command must point at the accepted modelo work surface."""
    recovery = build_recovery_for_overdue(days_late=18, modelo="130", period=Period.from_year_and_code(2026, "1T"))
    assert recovery.still_filable is True
    assert recovery.recargo_band.id == "within_30_days"
    assert "ley-58-2003" in recovery.legal_ref
    assert recovery.next_command == "aeat app modelo work --help"


def test_load_recargo_bands_wraps_missing_path_as_domain_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing-recargo-bands.toml"

    with pytest.raises(DeadlineValidationError, match=r"cannot stat recargo bracket registry"):
        load_recargo_bands(missing)
