"""The filing gate calls a declaration late on the same date the receipt does.

The obligation the deadline engine selects carries the close date the registry
declares. A window ending on a non-business day runs to the next business day
(Ley 39/2015 art. 30.5, applied to tax procedure through Ley 58/2003 art. 7.2),
so comparing the declared date against today refuses a filing on the shifted
day that the calculate posture, the declaration editor, the filing calendar and
the filing receipt's kept posture all call in time. The gate therefore reads the
close the engine published.

The reference date is a Europe/Madrid civil date (Ley 39/2015 art. 31,
peninsular official time at the sede electrónica). Europe/Madrid leads UTC, so
the UTC date of a filing instant stamped late on the Spanish evening is the
previous Spanish day; judging on it would call a late filing timely.

The window is scanned from the published authority rather than named here,
because the supported years and each modelo's editions are declared once in the
registry.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ....core.filing_timeliness import FilingTimeliness
from ....core.time.clock import MADRID_TZ, now
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.irpf_income_categories import require_irpf_income_category
from ....domain.contribuyente.entity_type import require_entity_type
from ....domain.deadlines.effective_close import resolve_effective_filing_deadline
from ....domain.deadlines.models import IVARegime, ModeloDeadline, TaxpayerProfile
from ....domain.deadlines.tests.effective_close_scan import ScannedObligation, obligation_with_a_shifted_close
from ..deadline_decisions import decide_filing_deadline
from ..run_models import WorkflowDeadlineContextDetails, WorkflowPurpose, WorkflowStage, WorkflowStep

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _scan_profile() -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X0001500M",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": IVARegime("GENERAL"),
            "has_employees": True,
            "pays_rent_with_retencion": True,
        },
    )


@pytest.fixture(name="scanned")
def _scanned(operation: PinnedAuthorityOperation) -> ScannedObligation:
    """A real obligation whose close moves to the next business day."""
    scanned = obligation_with_a_shifted_close(_scan_profile(), operation=operation)
    assert scanned.effective_closes_on > scanned.nominal_closes_on
    return scanned


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


def test_a_filing_on_the_shifted_close_is_not_marked_extemporanea(
    scanned: ScannedObligation,
    operation: PinnedAuthorityOperation,
) -> None:
    """The business day after a non-business close is inside the window."""
    details = _deadline_details(_decide(scanned.obligation, today=scanned.effective_closes_on, operation=operation))

    assert details.overdue is None
    assert details.extemporanea is None


def test_the_day_after_the_shifted_close_is_marked_extemporanea(
    scanned: ScannedObligation,
    operation: PinnedAuthorityOperation,
) -> None:
    """Past the effective close the gate records the late filing against that date."""
    day_after = scanned.effective_closes_on + timedelta(days=1)
    deadline = resolve_effective_filing_deadline(
        str(scanned.obligation.modelo),
        scanned.obligation.period.filing_year,
        scanned.obligation.period,
        operation=operation,
    )

    details = _deadline_details(_decide(scanned.obligation, today=day_after, operation=operation))

    assert details.overdue is True
    assert details.extemporanea is True
    assert details.closes_on == scanned.effective_closes_on, "lateness is recorded against the date it was judged on"
    assert deadline is not None
    assert deadline.timeliness_on(day_after) is FilingTimeliness.EXTEMPORANEA


def test_a_late_spanish_evening_filing_is_judged_on_the_spanish_civil_date(
    scanned: ScannedObligation,
    operation: PinnedAuthorityOperation,
) -> None:
    """The civil date of the filing instant decides, not its UTC date.

    A filing stamped at 23:30 UTC on the effective close happened on the
    following Spanish civil day and is extemporánea. The filing action feeds
    the gate that civil date, so the gate and the receipt's kept posture agree.
    """
    close = scanned.effective_closes_on
    filed_at = datetime(close.year, close.month, close.day, 23, 30, tzinfo=UTC)

    assert filed_at.date() == close, "the UTC date still reads as the closing day"
    assert filed_at.astimezone(MADRID_TZ).date() > close

    on_utc_date = _deadline_details(_decide(scanned.obligation, today=filed_at.date(), operation=operation))
    on_civil_date = _deadline_details(
        _decide(scanned.obligation, today=filed_at.astimezone(MADRID_TZ).date(), operation=operation)
    )

    assert on_utc_date.extemporanea is None
    assert on_civil_date.extemporanea is True
