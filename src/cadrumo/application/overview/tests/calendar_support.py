"""Shared resolvers, repositories and invoice builders for the ledger source-mesh tests."""

from __future__ import annotations

from datetime import date

from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import (
    ObligationStatus,
)
from ..calendar_models import (
    OverviewCalendarEntry,
    OverviewPeriodState,
)

_YEAR = filing_year_envelope().horizon

# ---------------------------------------------------------------------
# OverviewCalendarEntry
# ---------------------------------------------------------------------


def calendar_entry(**overrides: object) -> OverviewCalendarEntry:
    base: dict[str, object] = {
        "modelo": "130",
        "period": Period.from_year_and_code(_YEAR, "1T"),
        "opens_on": date(_YEAR, 4, 1),
        "closes_on": date(_YEAR, 4, 20),
        "adjusted_closes_on": date(_YEAR, 4, 20),
        "shift_reason": "business_day",
        "holiday_coverage": DeadlineHolidayCoverage.NATIONAL_ONLY,
        "holiday_refs": (),
        "jurisdictions": (),
        "payment_cutoff_on": date(_YEAR, 4, 15),
        "evaluated_on": date(_YEAR, 4, 1),
        "status": ObligationStatus.UPCOMING,
        "user_state": OverviewPeriodState.DUE,
    }
    base.update(overrides)
    return OverviewCalendarEntry.model_validate(base)
