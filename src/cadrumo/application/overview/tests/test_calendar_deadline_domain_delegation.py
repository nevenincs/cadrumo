"""Overview delegates window matching and status classification to the deadline domain.

The overview calendar used to carry its own copy of two deadline rules: it
scanned ``authority.deadline_windows(filing_year)`` for a matching registry
window, and it restated the OVERDUE / DUE_TODAY / DUE_SOON / UPCOMING
boundaries around ``closes_on``. Both copies AGREED with the deadline domain,
which is precisely what made them dangerous — a change to either rule could
move extemporaneidad and calendar placement independently, and no parity
assertion would have noticed until after they had already diverged.

That agreement also governs what can be proven here. A test asserting "overview
and the deadline domain return the same window / the same status" passes
whether or not overview delegates, because the duplicate produced the same
answers. Such assertions are SUPPORTING only. The DISCRIMINATING assertions in
this module therefore test the MECHANISM — that overview actually reaches the
canonical owner — so that removing the delegation fails them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ....core.filing_year import FOUR_DIGIT_YEAR_FIRST
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.effective_close import EffectiveFilingDeadline
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ObligationStatus
from ....domain.deadlines.plazo import resolve_filing_window
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..calendar import local_work_unit_status, registry_window_for_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Declared locally rather than imported from ``calendar_test_support``: that
# module resolves a registry snapshot at import time, which would couple the
# classification tests below to a registry load they do not need.
_BUCKET_ID = "7390a6bb-5577-4e08-8518-16e6292f690f"
_MODELO = "130"
_FILING_YEAR = filing_year_envelope().horizon
_DUE_SOON_DAYS = 14


def _work_unit(period_code: str = "1T") -> WorkUnit:
    """Build a real Modelo 130 work unit for a registry-covered period."""
    period = Period.from_year_and_code(_FILING_YEAR, period_code)
    revision_id = "deadline-domain-delegation"
    created_at = datetime(_FILING_YEAR, 1, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=ModeloCode(_MODELO),
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"delegation-{_MODELO}-{_FILING_YEAR}",
        created_at=created_at,
        updated_at=created_at,
    )


# ---------------------------------------------------------------------------
# F63 — one registry deadline-window resolver
# ---------------------------------------------------------------------------


def test_overview_window_lookup_goes_through_the_domain_resolver() -> None:
    """DISCRIMINATING: overview's lookup must reach the canonical resolver.

    The resolver is the domain's single matching authority. The compiled name
    reference distinguishes delegation from a local scan that happens to
    produce the same answer, so a duplicate matcher cannot satisfy this gate.
    """
    _work_unit()
    referenced = registry_window_for_work_unit.__code__.co_names
    assert "resolve_filing_window" in referenced, (
        "overview.registry_window_for_work_unit must delegate to "
        "domain.deadlines.resolve_filing_window; referenced names were "
        f"{referenced}"
    )


def test_overview_window_lookup_returns_the_domain_entry() -> None:
    """SUPPORTING: overview projects the same window as the domain resolver.

    The mechanism is pinned above; this assertion keeps the projection contract
    explicit while the deadline domain remains the sole matching authority.
    """
    unit = _work_unit()
    assert registry_window_for_work_unit(unit) == resolve_filing_window(
        _MODELO,
        _FILING_YEAR,
        unit.period,
    )


def test_overview_reads_the_published_first_quarter_close_date() -> None:
    """The overview window retains the published M130 Q1 closing date."""
    unit = _work_unit()
    window = registry_window_for_work_unit(unit)
    assert window is not None, "Modelo 130 1T must have a bundled registry deadline window"

    assert window.closes_on == date(_FILING_YEAR, 4, 20)


def test_overview_keeps_its_local_period_fallback_when_no_window_exists() -> None:
    """SUPPORTING: an unmatched target still yields ``None`` from the resolver.

    Overview's own fallback to the period date span depends on this contract,
    and the shared resolver must not start borrowing a neighbouring year's
    window to avoid returning ``None``.
    """
    unmatched = Period.from_year_and_code(FOUR_DIGIT_YEAR_FIRST, "1T")

    assert resolve_filing_window(_MODELO, FOUR_DIGIT_YEAR_FIRST, unmatched) is None


# ---------------------------------------------------------------------------
# F64 — one deadline posture
# ---------------------------------------------------------------------------


def _deadline(coverage: DeadlineHolidayCoverage, *, closes_on: date) -> EffectiveFilingDeadline:
    return EffectiveFilingDeadline(
        nominal_closes_on=closes_on,
        closes_on=closes_on,
        holiday_coverage=coverage,
        shift_reason="no_shift",
    )


def test_overview_status_reads_the_canonical_posture() -> None:
    """DISCRIMINATING: overview must delegate its date boundaries.

    A restated implementation compares dates and names ``ObligationStatus``
    members inline; the compiled name references show whether overview reads
    the posture the deadline domain owns instead.
    """
    referenced = local_work_unit_status.__code__.co_names

    assert "posture_on" in referenced, (
        f"overview.local_work_unit_status must read EffectiveFilingDeadline.posture_on; referenced names were "
        f"{referenced}"
    )


def test_overview_filing_gate_short_circuits_before_the_posture() -> None:
    """DISCRIMINATING: the filed-pointer gate is the one intentional difference.

    A unit carrying a filing pointer must report FILED even on a date the
    canonical posture calls OVERDUE.
    """
    unit = _work_unit().model_copy(update={"current_filing_record_id": "filing-record-1"})
    deadline = _deadline(DeadlineHolidayCoverage.NATIONAL_ONLY, closes_on=unit.period.end_date)
    today = deadline.closes_on + timedelta(days=1)

    assert deadline.posture_on(today, due_soon_days=_DUE_SOON_DAYS).status is ObligationStatus.OVERDUE
    assert local_work_unit_status(unit, deadline, today, _DUE_SOON_DAYS) is ObligationStatus.FILED


@pytest.mark.parametrize(
    "coverage",
    [DeadlineHolidayCoverage.NATIONAL_ONLY, DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE],
    ids=["known-close", "unknown-close"],
)
@pytest.mark.parametrize("offset_days", [-15, -14, -1, 0, 1], ids=lambda days: f"day{days:+d}")
def test_unfiled_work_unit_reads_the_posture_at_every_boundary(
    coverage: DeadlineHolidayCoverage,
    offset_days: int,
) -> None:
    """An unfiled work unit's status is exactly the posture, known close or not.

    Before the posture owned it, overview classified a work unit whose shift
    calendar was unpublished against its nominal date and called it overdue
    while the schedule called the same window unknown.
    """
    unit = _work_unit()
    deadline = _deadline(coverage, closes_on=unit.period.end_date)
    today = deadline.closes_on + timedelta(days=offset_days)

    expected = deadline.posture_on(today, due_soon_days=_DUE_SOON_DAYS).status

    assert local_work_unit_status(unit, deadline, today, _DUE_SOON_DAYS) is expected
    if coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE:
        assert expected is ObligationStatus.UNKNOWN
