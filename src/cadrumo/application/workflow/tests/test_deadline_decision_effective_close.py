"""The filing gate calls a declaration late on the same date the receipt does.

The obligation the deadline engine selects carries the close date the registry
declares. A window ending on a non-business day runs to the next business day
(Ley 39/2015 art. 30.5, applied to tax procedure through Ley 58/2003 art. 7.2),
so comparing the declared date against today refuses a filing on the shifted
day that the calculate posture, the declaration editor, the filing calendar and
the filing receipt's kept posture all call in time. The gate therefore reads
the one shared effective-deadline projection.

The reference date is a Europe/Madrid civil date (Ley 39/2015 art. 31,
peninsular official time at the sede electrónica). Europe/Madrid leads UTC by
two hours in April, so the UTC date of a filing instant stamped late on the
Spanish evening is the previous Spanish day; judging on it would call a late
filing timely for two hours every night.

Modelo 136 1T 2025 is the case: the registry declares Sunday 20 April 2025 and
the filer has until Monday the 21st.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ....core.filing_timeliness import FilingTimeliness
from ....core.period import Period
from ....core.time.clock import MADRID_TZ, now
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.models import ModeloDeadline, ObligationStatus
from ...modelo.effective_deadline import resolve_effective_filing_deadline
from ..deadline_decisions import decide_filing_deadline
from ..run_models import WorkflowDeadlineContextDetails, WorkflowPurpose, WorkflowStage, WorkflowStep

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "136"
_FILING_YEAR = 2025
_PERIOD_CODE = "1T"


def _registry_obligation(operation: PinnedAuthorityOperation) -> ModeloDeadline:
    """Build the obligation the schedule carries, with the registry's own dates."""
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    deadline = resolve_effective_filing_deadline(_MODELO, _FILING_YEAR, period, operation=operation)
    assert deadline is not None
    assert deadline.nominal_closes_on.weekday() == 6, "the 136 1T 2025 window still closes nominally on a Sunday"
    assert deadline.closes_on > deadline.nominal_closes_on, "the effective close is still the next business day"
    return ModeloDeadline(
        modelo=_MODELO,
        period=period,
        opens_on=date(_FILING_YEAR, 4, 1),
        closes_on=deadline.nominal_closes_on,
        status=ObligationStatus.OVERDUE,
    )


def _decide(obligation: ModeloDeadline, *, today: date, operation: PinnedAuthorityOperation) -> list[WorkflowStep]:
    steps: list[WorkflowStep] = []
    decide_filing_deadline(
        obligation=obligation,
        target_modelo=obligation.modelo,
        target_period=obligation.period,
        today=today,
        started=now(),
        steps=steps,
        purpose=WorkflowPurpose.FILE,
        authority_operation=operation,
    )
    return steps


def _deadline_details(steps: list[WorkflowStep]) -> WorkflowDeadlineContextDetails:
    step = next(step for step in steps if step.stage is WorkflowStage.COMPUTING_DEADLINES)
    assert isinstance(step.details, WorkflowDeadlineContextDetails)
    return step.details


def test_a_filing_on_the_shifted_close_is_not_marked_extemporanea(operation: PinnedAuthorityOperation) -> None:
    """The Monday after a Sunday close is inside the window, not one day late."""
    obligation = _registry_obligation(operation)
    deadline = resolve_effective_filing_deadline(_MODELO, _FILING_YEAR, obligation.period, operation=operation)
    assert deadline is not None

    details = _deadline_details(_decide(obligation, today=deadline.closes_on, operation=operation))

    assert details.overdue is None
    assert details.extemporanea is None
    assert details.closes_on == obligation.closes_on


def test_the_day_after_the_shifted_close_is_marked_extemporanea(operation: PinnedAuthorityOperation) -> None:
    """Past the effective close the gate records the late filing against that date."""
    obligation = _registry_obligation(operation)
    deadline = resolve_effective_filing_deadline(_MODELO, _FILING_YEAR, obligation.period, operation=operation)
    assert deadline is not None
    day_after = deadline.closes_on + timedelta(days=1)

    details = _deadline_details(_decide(obligation, today=day_after, operation=operation))

    assert details.overdue is True
    assert details.extemporanea is True
    assert details.closes_on == deadline.closes_on, "lateness is recorded against the date it was judged on"
    assert deadline.timeliness_on(day_after) is FilingTimeliness.EXTEMPORANEA


def test_a_late_spanish_evening_filing_is_judged_on_the_spanish_civil_date(
    operation: PinnedAuthorityOperation,
) -> None:
    """The civil date of the filing instant decides, not its UTC date.

    A filing stamped at 22:30 UTC on the effective close happened on the
    following Spanish civil day and is extemporánea. The filing action feeds
    the gate that civil date, so the gate and the receipt's kept posture agree.
    """
    obligation = _registry_obligation(operation)
    deadline = resolve_effective_filing_deadline(_MODELO, _FILING_YEAR, obligation.period, operation=operation)
    assert deadline is not None
    filed_at = datetime(deadline.closes_on.year, deadline.closes_on.month, deadline.closes_on.day, 22, 30, tzinfo=UTC)
    assert filed_at.date() == deadline.closes_on, "the UTC date still reads as the closing day"
    assert filed_at.astimezone(MADRID_TZ).date() > deadline.closes_on

    on_utc_date = _deadline_details(_decide(obligation, today=filed_at.date(), operation=operation))
    on_civil_date = _deadline_details(
        _decide(obligation, today=filed_at.astimezone(MADRID_TZ).date(), operation=operation)
    )

    assert on_utc_date.extemporanea is None
    assert on_civil_date.extemporanea is True
    assert deadline.timeliness_on(filed_at.astimezone(MADRID_TZ).date()) is FilingTimeliness.EXTEMPORANEA
