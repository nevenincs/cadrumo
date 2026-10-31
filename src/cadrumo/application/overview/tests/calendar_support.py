"""Shared resolvers, repositories and invoice builders for the ledger source-mesh tests."""

from __future__ import annotations

from datetime import date

from ....core.period import Period
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import (
    ObligationStatus,
)
from ..calendar_models import (
    OverviewCalendarEntry,
    OverviewPeriodState,
)

# ---------------------------------------------------------------------
# OverviewCalendarEntry
# ---------------------------------------------------------------------


def _entry(**overrides: object) -> OverviewCalendarEntry:
    base: dict[str, object] = {
        "modelo": "130",
        "period": Period.from_year_and_code(2026, "1T"),
        "opens_on": date(2026, 4, 1),
        "closes_on": date(2026, 4, 20),
        "adjusted_closes_on": date(2026, 4, 20),
        "shift_reason": "business_day",
        "holiday_coverage": DeadlineHolidayCoverage.NATIONAL_ONLY,
        "holiday_refs": (),
        "jurisdictions": (),
        "payment_cutoff_on": date(2026, 4, 15),
        "evaluated_on": date(2026, 4, 1),
        "status": ObligationStatus.UPCOMING,
        "user_state": OverviewPeriodState.DUE,
    }
    base.update(overrides)
    return OverviewCalendarEntry.model_validate(base)
