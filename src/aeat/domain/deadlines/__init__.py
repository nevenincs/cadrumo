"""Registry-backed filing-deadline computation engine for autónomo profiles.

:class:`DeadlineEngine` is the project's first user-visible
"answer-the-user" surface: given an :class:`AutonomoProfile` and a
year, it produces a deterministic typed :class:`Schedule` of every
filing the autónomo is obliged to submit, with concrete opens /
closes dates and a current :class:`ObligationStatus`.

The engine is read-only — it never touches the storage layer, never
files anything, and never mutates its inputs.

Examples:
    >>> from datetime import date
    >>> from aeat.domain.deadlines import (
    ...     AutonomoProfile,
    ...     DeadlineEngine,
    ...     IVARegime,
    ...     next_deadline,
    ... )
    >>> profile = AutonomoProfile(
    ...     tax_id="X1234567L",
    ...     iva_regime=IVARegime.GENERAL,
    ...     has_employees=False,
    ...     pays_rent_with_retencion=True,
    ...     does_intracomunitario=False,
    ...     bienes_extranjero_above_threshold=False,
    ... )
    >>> engine = DeadlineEngine()
    >>> schedule = engine.compute(profile, year=2026, today=date(2026, 4, 1))
    >>> _ = next_deadline(schedule, today=date(2026, 4, 1))
"""

from __future__ import annotations

from .._identifiers import ModeloIdentifier
from ._engine import (
    DeadlineEngine,
    ScheduleProducer,
    applies_to,
    compute_obligation_schedule,
    explain,
    next_deadline,
)
from ._errors import (
    DeadlineError,
    ProfileError,
    ScheduleComputationError,
)
from ._festivos import (
    MODELOS_WITHOUT_SHIFT,
    CalendarCCAA,
    DeadlineShift,
    Holiday,
    HolidayCalendar,
    HolidayJurisdiction,
    is_business_day,
    load_holiday_calendar,
    next_business_day,
    shift_deadline,
)
from ._models import (
    AutonomoProfile,
    IVARegime,
    ModeloDeadline,
    ModeloEnrollment,
    ModeloIVAProfile,
    ObligationStatus,
    RecargoBand,
    Recovery,
    Schedule,
)
from ._profiles import autonomo_profile_from_mapping
from ._recargo import (
    build_recovery_for_overdue,
    load_recargo_bands,
    resolve_recargo_band,
)

__all__ = [
    "MODELOS_WITHOUT_SHIFT",
    "AutonomoProfile",
    "CalendarCCAA",
    "DeadlineEngine",
    "DeadlineError",
    "DeadlineShift",
    "Holiday",
    "HolidayCalendar",
    "HolidayJurisdiction",
    "IVARegime",
    "ModeloDeadline",
    "ModeloEnrollment",
    "ModeloIVAProfile",
    "ModeloIdentifier",
    "ObligationStatus",
    "ProfileError",
    "RecargoBand",
    "Recovery",
    "Schedule",
    "ScheduleComputationError",
    "ScheduleProducer",
    "applies_to",
    "autonomo_profile_from_mapping",
    "build_recovery_for_overdue",
    "compute_obligation_schedule",
    "explain",
    "is_business_day",
    "load_holiday_calendar",
    "load_recargo_bands",
    "next_business_day",
    "next_deadline",
    "resolve_recargo_band",
    "shift_deadline",
]
