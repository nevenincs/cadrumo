"""The canonical deadline posture of one effective close, pinned at every boundary.

:meth:`EffectiveFilingDeadline.posture_on` is the single judgement of a
reference date against a declaration's close: the schedule's status, the
calendar row, the declaration editor's day counts, the calculate posture and
the filing receipt's timeliness all read it. These cases build the value in
memory around an arbitrary close, so they address no registry edition and no
filing year: the posture is a function of the close, its holiday coverage and
the reference date alone.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ....core.filing_timeliness import FilingTimeliness
from ..effective_close import DEFAULT_DUE_SOON_DAYS, EffectiveFilingDeadline
from ..festivos import CALENDAR_UNAVAILABLE_SHIFT_REASON, DeadlineHolidayCoverage
from ..models import ObligationStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOMINAL = date.fromordinal(739_000)
_SHIFT = timedelta(days=2)
_DAY = timedelta(days=1)


def _known(*, shifted: bool) -> EffectiveFilingDeadline:
    return EffectiveFilingDeadline(
        nominal_closes_on=_NOMINAL,
        closes_on=_NOMINAL + _SHIFT if shifted else _NOMINAL,
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        shift_reason="business_day" if shifted else "no_shift",
    )


def _unknown() -> EffectiveFilingDeadline:
    return EffectiveFilingDeadline(
        nominal_closes_on=_NOMINAL,
        closes_on=_NOMINAL,
        holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
        shift_reason=CALENDAR_UNAVAILABLE_SHIFT_REASON,
    )


@pytest.mark.parametrize("shifted", [False, True], ids=["unshifted", "shifted"])
@pytest.mark.parametrize(
    ("offset_days", "status", "remaining", "overdue", "timeliness"),
    [
        (-(DEFAULT_DUE_SOON_DAYS + 1), ObligationStatus.UPCOMING, DEFAULT_DUE_SOON_DAYS + 1, None, "en_plazo"),
        (-DEFAULT_DUE_SOON_DAYS, ObligationStatus.DUE_SOON, DEFAULT_DUE_SOON_DAYS, None, "en_plazo"),
        (-1, ObligationStatus.DUE_SOON, 1, None, "en_plazo"),
        (0, ObligationStatus.DUE_TODAY, 0, None, "en_plazo"),
        (1, ObligationStatus.OVERDUE, None, 1, "extemporanea"),
    ],
)
def test_a_known_close_is_judged_against_the_effective_date(
    shifted: bool,
    offset_days: int,
    status: ObligationStatus,
    remaining: int | None,
    overdue: int | None,
    timeliness: str,
) -> None:
    """Every boundary falls relative to the effective close, never the nominal one."""
    deadline = _known(shifted=shifted)
    reference = deadline.closes_on + timedelta(days=offset_days)

    posture = deadline.posture_on(reference)

    assert posture.status is status
    assert posture.days_remaining == remaining
    assert posture.days_overdue == overdue
    assert deadline.timeliness_on(reference) is FilingTimeliness(timeliness)


def test_the_day_after_the_nominal_close_of_a_shifted_close_is_still_in_plazo() -> None:
    """The nominal-close classification this module replaced called this day overdue."""
    deadline = _known(shifted=True)
    reference = _NOMINAL + _DAY

    posture = deadline.posture_on(reference)

    assert posture.status is ObligationStatus.DUE_SOON
    assert posture.days_overdue is None
    assert posture.days_remaining == (_SHIFT - _DAY).days
    assert deadline.timeliness_on(reference) is FilingTimeliness.EN_PLAZO


def test_a_zero_due_soon_window_leaves_only_due_today_and_upcoming() -> None:
    deadline = _known(shifted=False)

    assert deadline.posture_on(_NOMINAL - _DAY, due_soon_days=0).status is ObligationStatus.UPCOMING
    assert deadline.posture_on(_NOMINAL, due_soon_days=0).status is ObligationStatus.DUE_TODAY
    assert deadline.posture_on(_NOMINAL + _DAY, due_soon_days=0).status is ObligationStatus.OVERDUE


def test_an_unknown_close_is_unknown_and_never_overdue() -> None:
    """An unpublished shift calendar keeps the nominal date only as a lower bound."""
    deadline = _unknown()

    assert deadline.close_known is False
    before = deadline.posture_on(_NOMINAL - _DAY)
    on = deadline.posture_on(_NOMINAL)
    after = deadline.posture_on(_NOMINAL + _DAY)

    assert (before.status, before.days_remaining, before.days_overdue) == (ObligationStatus.UNKNOWN, 1, None)
    assert (on.status, on.days_remaining, on.days_overdue) == (ObligationStatus.UNKNOWN, 0, None)
    assert (after.status, after.days_remaining, after.days_overdue) == (ObligationStatus.UNKNOWN, None, None)
    assert deadline.timeliness_on(_NOMINAL) is FilingTimeliness.EN_PLAZO
    assert deadline.timeliness_on(_NOMINAL + _DAY) is FilingTimeliness.UNKNOWN


def test_an_unknown_close_cannot_carry_a_shifted_date() -> None:
    with pytest.raises(ValueError, match="unknown close keeps only the nominal date"):
        EffectiveFilingDeadline(
            nominal_closes_on=_NOMINAL,
            closes_on=_NOMINAL + _DAY,
            holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
            shift_reason=CALENDAR_UNAVAILABLE_SHIFT_REASON,
        )
