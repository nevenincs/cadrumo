"""Tests for the Ley 58/2003 art-27.2 recargo band loader and resolver.

External authority: Ley 58/2003 (LGT) Art. 27.2, post-Ley 11/2021. The recargo
is 1% plus a further 1% per COMPLETED month of delay, with no intereses de
demora for the first 12 months; once 12 completed months elapse the recargo is
15% plus intereses de demora. A fractional month does NOT count ("por cada mes
completo de retraso"), so the schedule is keyed on completed months.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from .._errors import DeadlineValidationError
from .._recargo import (
    build_recovery_for_overdue,
    completed_months_late,
    load_recargo_bands,
    resolve_recargo_band,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_recargo_bands_load_from_registry_toml_in_order() -> None:
    """The band TOML must materialise sorted by min_completed_months.

    External authority: ley-58-2003:art-27.2 (Ley General Tributaria,
    post-Ley 11/2021). The canonical TOML lives at
    ``registry/aeat/legal/ley-58-2003-recargo-bands.toml``.
    """
    bands = load_recargo_bands()
    assert len(bands) >= 4
    # Sorted ascending by lower bound (0, 1, 2, ...).
    prior = -1
    for band in bands:
        assert band.min_completed_months > prior
        prior = band.min_completed_months
    # Every band carries the Ley 58/2003 reference.
    assert all("ley-58-2003" in band.legal_ref for band in bands)
    # Exactly one band has interest_applies=True (the after-12-months tail).
    interest_bands = [b for b in bands if b.interest_applies]
    assert len(interest_bands) == 1
    assert interest_bands[0].max_completed_months is None


def test_zero_completed_months_yields_1_pct() -> None:
    """Filed late but within the first incomplete month → 1% base, no interest."""
    bands = load_recargo_bands()
    band = resolve_recargo_band(0, bands)
    assert band.surcharge_pct == Decimal("1.00")
    assert band.interest_applies is False


def test_one_completed_month_yields_2_pct() -> None:
    """1 completed month → 1% base + 1% = 2% (Art. 27.2, per completed month)."""
    bands = load_recargo_bands()
    band = resolve_recargo_band(1, bands)
    assert band.surcharge_pct == Decimal("2.00")
    assert band.interest_applies is False


def test_five_completed_months_yields_6_pct() -> None:
    """5 completed months → 1% + 5% = 6%."""
    bands = load_recargo_bands()
    band = resolve_recargo_band(5, bands)
    assert band.surcharge_pct == Decimal("6.00")
    assert band.interest_applies is False


def test_after_12_completed_months_adds_interest() -> None:
    """At/after 12 completed months the 15% + interest band applies."""
    bands = load_recargo_bands()
    band = resolve_recargo_band(13, bands)
    assert band.id == "after_12_months"
    assert band.surcharge_pct == Decimal("15.00")
    assert band.interest_applies is True


def test_resolve_recargo_band_rejects_negative_completed_months() -> None:
    bands = load_recargo_bands()
    with pytest.raises(ValueError, match="completed_months must be >= 0"):
        resolve_recargo_band(-1, bands)


def test_completed_months_counts_only_whole_months() -> None:
    """A month is completed only when the day-of-month is reached (Art. 27.2).

    Deadline 2026-04-20: at 2026-05-19 zero completed months (1 day short of
    the May-20 anniversary); at 2026-05-20 exactly one completed month.
    """
    closes = date(2026, 4, 20)
    assert completed_months_late(closes, date(2026, 5, 19)) == 0
    assert completed_months_late(closes, date(2026, 5, 20)) == 1
    assert completed_months_late(closes, date(2026, 6, 20)) == 2
    assert completed_months_late(closes, closes) == 0


def test_build_recovery_uses_completed_months_not_day_bracket() -> None:
    """A filing ~1 completed month late carries 2%, not a coarse bracket midpoint.

    Deadline 2026-04-20, presented 2026-06-19 → 1 completed month (the June-20
    anniversary is not yet reached) → 2% per Art. 27.2. The pre-fix day-bracket
    table returned 3% for this case; the completed-month computation is exact.
    """
    recovery = build_recovery_for_overdue(
        closes_on=date(2026, 4, 20),
        reference_today=date(2026, 6, 19),
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
    )
    assert recovery.still_filable is True
    assert recovery.recargo_band.surcharge_pct == Decimal("2.00")
    assert recovery.recargo_band.interest_applies is False
    assert "ley-58-2003" in recovery.legal_ref
    assert recovery.next_command == "aeat app modelo work --help"


def test_load_recargo_bands_wraps_missing_path_as_domain_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing-recargo-bands.toml"

    with pytest.raises(DeadlineValidationError, match=r"cannot stat recargo bracket registry"):
        load_recargo_bands(missing)
