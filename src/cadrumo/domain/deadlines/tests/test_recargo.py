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
from pydantic import ValidationError

from ....core import Period
from ..errors import DeadlineValidationError
from .._models import Recovery
from .._recargo import (
    build_recovery_for_overdue,
    completed_months_late,
    load_recargo_bands,
    more_than_twelve_months_elapsed,
    resolve_recargo_band,
    twelve_month_anniversary,
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


def test_twelve_completed_months_yields_13_pct_no_interest() -> None:
    """Exactly 12 completed months → 1% + 12% = 13%, still no interest (Art. 27.2).

    The graduated "1 por ciento más otro 1 por ciento adicional por cada mes
    completo de retraso" reaches its maximum, 13%, at the twelve-month
    anniversary. The 15% + intereses tail only applies once the twelve months
    have been exceeded (see the boundary tests below), so 12 completed months is
    still graduated.
    """
    bands = load_recargo_bands()
    band = resolve_recargo_band(12, bands)
    assert band.id == "completed_months_12"
    assert band.surcharge_pct == Decimal("13.00")
    assert band.interest_applies is False


def test_after_12_completed_months_adds_interest() -> None:
    """At/after 13 completed months the 15% + interest tail band applies.

    Thirteen completed months is unambiguously past the twelve-month term (a
    completed thirteenth month can only exist strictly beyond twelve months), so
    the 15% + intereses de demora tail is correct here (Art. 27.2 LGT).
    """
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
    assert "ley-58-2003" in recovery.recargo_band.legal_ref
    assert "next_command" not in type(recovery).model_fields


def test_load_recargo_bands_wraps_missing_path_as_domain_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing-recargo-bands.toml"

    with pytest.raises(DeadlineValidationError, match=r"cannot stat recargo bracket registry"):
        load_recargo_bands(missing)


# ---------------------------------------------------------------------------
# Art. 27.2 LGT — exact twelve-month boundary (the anniversary belongs to the
# graduated band; the 15% + intereses tail begins the DAY AFTER)
# ---------------------------------------------------------------------------


def test_twelve_month_anniversary_is_same_day_next_year() -> None:
    """The twelve-month term is the same day-of-month twelve months later."""
    assert twelve_month_anniversary(date(2026, 4, 20)) == date(2027, 4, 20)
    assert twelve_month_anniversary(date(2026, 1, 30)) == date(2027, 1, 30)


def test_twelve_month_anniversary_clamps_leap_day() -> None:
    """A 29 February close clamps to 28 February in a non-leap target year."""
    assert twelve_month_anniversary(date(2024, 2, 29)) == date(2025, 2, 28)


def test_more_than_twelve_months_elapsed_is_strict_after_anniversary() -> None:
    """The 15% tail predicate fires strictly AFTER the anniversary, not on it.

    External authority: Ley 58/2003 Art. 27.2 — the 15% + intereses tail applies
    "una vez transcurridos 12 meses", and intereses run "desde el día siguiente al
    término de los 12 meses". So the anniversary is not yet the tail; the day
    after is.
    """
    closes = date(2026, 4, 20)
    assert more_than_twelve_months_elapsed(closes, date(2027, 4, 19)) is False
    assert more_than_twelve_months_elapsed(closes, date(2027, 4, 20)) is False
    assert more_than_twelve_months_elapsed(closes, date(2027, 4, 21)) is True


def test_exact_twelve_month_anniversary_stays_in_graduated_band() -> None:
    """The exact twelve-month anniversary resolves to 13% graduated, NOT the 15% tail.

    Regression for the cross-domain-continuity audit finding
    ``articulo-27-exact-twelve-month-boundary``: the demonstrated runtime case
    (plazo 2026-04-20, presented 2027-04-20 — exactly twelve months later) wrongly
    resolved to the 15% + intereses tail. Per Art. 27.2 LGT the anniversary is the
    ``término`` of the twelve-month period and still belongs to the graduated
    1%-per-completed-month band: 12 completed months → 1% + 12% = 13%, no interest.
    """
    recovery = build_recovery_for_overdue(
        closes_on=date(2026, 4, 20),
        reference_today=date(2027, 4, 20),
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
    )
    assert recovery.recargo_band.id == "completed_months_12"
    assert recovery.recargo_band.surcharge_pct == Decimal("13.00")
    assert recovery.recargo_band.interest_applies is False


def test_day_after_twelve_month_anniversary_enters_interest_tail() -> None:
    """The day after the twelve-month anniversary is the first 15% + intereses day.

    Art. 27.2 LGT: intereses de demora run "desde el día siguiente al término de
    los 12 meses", so 2027-04-21 (one day past the 2027-04-20 anniversary of a
    2026-04-20 plazo) is the first day of the 15% + intereses tail — even though it
    still reports only twelve completed months.
    """
    recovery = build_recovery_for_overdue(
        closes_on=date(2026, 4, 20),
        reference_today=date(2027, 4, 21),
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
    )
    assert recovery.recargo_band.id == "after_12_months"
    assert recovery.recargo_band.surcharge_pct == Decimal("15.00")
    assert recovery.recargo_band.interest_applies is True


def test_recovery_cannot_carry_a_legal_ref_contradicting_its_band() -> None:
    """The grounding has exactly one home, so two copies cannot disagree.

    ``Recovery`` used to mirror ``recargo_band.legal_ref`` onto a top-level
    ``legal_ref`` with no equality invariant, so a payload could be built whose
    top-level reference contradicted its nested one and both survived
    ``model_dump()``. A renderer reading whichever slot it happened to know
    about would then cite a different provision than the band it displays.

    Removing the mirror makes the contradiction unconstructible rather than
    merely discouraged: ``Recovery`` is ``extra="forbid"``, so supplying the
    retired field is refused outright.
    """
    recovery = build_recovery_for_overdue(
        closes_on=date(2026, 4, 20),
        reference_today=date(2026, 5, 21),
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
    )

    # The grounding is still reachable, and from one place only.
    assert "ley-58-2003" in recovery.recargo_band.legal_ref
    assert not hasattr(recovery, "legal_ref")

    with pytest.raises(ValidationError):
        Recovery(
            still_filable=True,
            recargo_band=recovery.recargo_band,
            legal_ref="not-canonical",
        )
