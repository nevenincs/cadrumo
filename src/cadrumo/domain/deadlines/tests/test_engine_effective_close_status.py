"""An obligation is not overdue on a day its filer may still file.

A filing window's published close is the nominal date on the national basis. A
window whose close falls on a Saturday, Sunday or national inhábil runs to the
next business day (Ley 39/2015 art. 30.5, applied to tax procedure through Ley
58/2003 art. 7.2). Classifying the obligation against the nominal date called
the filer late on a day the plazo was still open, and the recargo it attached
counted from the wrong deadline.

Modelo 136 1T 2025 is the case the registry provides: its window closes
nominally on Sunday 20 April 2025, so the filer has until Monday the 21st.

Where the shift's own holiday calendar is not published, the effective close is
unknown. Such an obligation is ``UNKNOWN`` and carries no payment cutoff and no
recovery: nothing is judged after a date that is only a lower bound.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.irpf_income_categories import require_irpf_income_category
from ...contribuyente.entity_type import require_entity_type
from ..effective_close import effective_filing_deadline
from ..engine import DeadlineEngine
from ..festivos import DeadlineHolidayCoverage
from ..models import IVARegime, ModeloDeadline, ObligationStatus, TaxpayerProfile

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_MODELO = Modelo("136")
_FILING_YEAR = 2025
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "1T")


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X0001500M",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": IVARegime("GENERAL"),
            "premio_loteria_gravamen_especial_sin_retencion": True,
            "premio_loteria_gravamen_especial_trimestres": frozenset({"2025-1T"}),
        },
    )


def _obligation(*, today: date, operation: PinnedAuthorityOperation) -> ModeloDeadline:
    schedule = DeadlineEngine(authority=operation).compute(_profile(), _FILING_YEAR, today=today)
    rows = [row for row in schedule.obligations if row.modelo == _MODELO and row.period == _PERIOD]
    assert len(rows) == 1, f"the engine lists Modelo {_MODELO} {_PERIOD} once"
    return rows[0]


def _close_dates(operation: PinnedAuthorityOperation) -> tuple[date, date]:
    """Return the nominal and effective closes the registry and shift rule give."""
    obligation = _obligation(today=date(_FILING_YEAR, 1, 2), operation=operation)
    effective = effective_filing_deadline(obligation.closes_on, modelo=str(_MODELO), operation=operation)
    assert obligation.closes_on.weekday() == 6, "the 136 1T 2025 window still closes nominally on a Sunday"
    assert effective.closes_on > obligation.closes_on
    return obligation.closes_on, effective.closes_on


def test_the_obligation_publishes_both_closes(operation: PinnedAuthorityOperation) -> None:
    """``closes_on`` keeps its published meaning; the shifted date travels beside it."""
    nominal, effective = _close_dates(operation)
    obligation = _obligation(today=date(_FILING_YEAR, 1, 2), operation=operation)

    assert obligation.closes_on == nominal
    assert obligation.adjusted_closes_on == effective
    assert obligation.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY
    assert obligation.shift_reason == "domingo", "the Sunday is the reason the close moved"


def test_the_shifted_close_day_is_due_today_not_overdue(operation: PinnedAuthorityOperation) -> None:
    """On the Monday the filer still has, the obligation is due, not late."""
    _nominal, effective = _close_dates(operation)
    obligation = _obligation(today=effective, operation=operation)

    assert obligation.status is ObligationStatus.DUE_TODAY
    assert obligation.recovery is None


def test_the_nominal_close_day_is_still_open(operation: PinnedAuthorityOperation) -> None:
    """The Sunday is inside the window, with one day left, not the last day."""
    nominal, _effective = _close_dates(operation)
    obligation = _obligation(today=nominal, operation=operation)

    assert obligation.status is ObligationStatus.DUE_SOON


def test_the_day_after_the_shifted_close_is_overdue(operation: PinnedAuthorityOperation) -> None:
    """Lateness and its recargo start the day after the effective close."""
    _nominal, effective = _close_dates(operation)
    obligation = _obligation(today=effective + timedelta(days=1), operation=operation)

    assert obligation.status is ObligationStatus.OVERDUE
    assert obligation.recovery is not None, "the art. 27 band is resolved from the effective close"


def test_a_year_whose_shift_calendar_is_unpublished_is_unknown_not_overdue(
    operation: PinnedAuthorityOperation,
) -> None:
    """An unknown effective close judges nothing after the nominal date.

    The 2022 holiday calendar is not bundled, so the shift cannot be resolved
    and the obligation reports its calendar unavailable. It is never called due
    or overdue against the nominal close, and carries no payment cutoff and no
    recargo.
    """
    schedule = DeadlineEngine(authority=operation).compute(_profile(), 2022, today=date(2026, 1, 2))
    unknown = [
        row for row in schedule.obligations if row.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    ]

    assert unknown, "expected at least one obligation whose shift calendar is unpublished"
    for row in unknown:
        assert row.status is ObligationStatus.UNKNOWN, row.modelo
        assert row.adjusted_closes_on == row.closes_on, row.modelo
        assert row.payment_cutoff_on is None, row.modelo
        assert row.recovery is None, row.modelo
