"""Registry-backed filing-deadline computation engine for taxpayer profiles.

:class:`DeadlineEngine` is the project's first user-visible
"answer-the-user" surface: given an :class:`TaxpayerProfile` and a
year, it produces a deterministic typed :class:`Schedule` of every
filing the taxpayer profile is obliged to submit, with concrete
opens / closes dates and a current :class:`ObligationStatus`.

The engine is read-only — it never touches the storage layer, never
files anything, and never mutates its inputs.

See Also:
    :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`
        Registry authority that supplies modelo deadline windows and
        applicability predicates consumed by :class:`DeadlineEngine`.
    :func:`compute_obligation_schedule`
        Single producer used by workflow gates and state projections to avoid
        divergent pending-obligation calculations.
    :func:`taxpayer_profile_from_mapping`
        Profile-value mapper used by application profile projections before
        calling this domain engine.
    :mod:`aeat.application.workflow`
        Application workflow gate that evaluates deadline obligations before
        verification and local filing steps.
    :mod:`aeat.application.overview`
        Local overview read model that merges this schedule with stored filing
        evidence.

Examples:
    >>> from datetime import date
    >>> from aeat.domain.deadlines import (
    ...     TaxpayerProfile,
    ...     DeadlineEngine,
    ...     IVARegime,
    ...     next_deadline,
    ... )
    >>> profile = TaxpayerProfile(
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
    DeadlineValidationError,
    NoDeadlineWindowsError,
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
    CrossPeriodGroupMemberRoster,
    EntityType,
    FiscalResidency,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    LegalEntityForm,
    ModeloDeadline,
    ModeloEnrollment,
    ModeloIVAProfile,
    ObligationStatus,
    RecargoBand,
    Recovery,
    RefundAccount,
    Schedule,
    TaxpayerProfile,
    evaluate_multiple_pagadores_obligation,
    irnr_representante_fiscal_required,
    is_ue_eee_country_code,
)
from ._plazo import resolve_filing_closes_on
from ._profiles import taxpayer_profile_from_mapping
from ._recargo import (
    build_recovery_for_overdue,
    completed_months_late,
    load_recargo_bands,
    resolve_recargo_band,
)

__all__ = [
    "MODELOS_WITHOUT_SHIFT",
    "CalendarCCAA",
    "CrossPeriodGroupMemberRoster",
    "DeadlineEngine",
    "DeadlineError",
    "DeadlineShift",
    "DeadlineValidationError",
    "EntityType",
    "FiscalResidency",
    "Holiday",
    "HolidayCalendar",
    "HolidayJurisdiction",
    "IVARegime",
    "IrpfEstimationRegime",
    "IrpfIncomeCategory",
    "IrpfSpecialRegime",
    "LegalEntityForm",
    "ModeloDeadline",
    "ModeloEnrollment",
    "ModeloIVAProfile",
    "NoDeadlineWindowsError",
    "ObligationStatus",
    "ProfileError",
    "RecargoBand",
    "Recovery",
    "RefundAccount",
    "Schedule",
    "ScheduleComputationError",
    "ScheduleProducer",
    "TaxpayerProfile",
    "applies_to",
    "build_recovery_for_overdue",
    "completed_months_late",
    "compute_obligation_schedule",
    "evaluate_multiple_pagadores_obligation",
    "explain",
    "irnr_representante_fiscal_required",
    "is_business_day",
    "is_ue_eee_country_code",
    "load_holiday_calendar",
    "load_recargo_bands",
    "next_business_day",
    "next_deadline",
    "resolve_filing_closes_on",
    "resolve_recargo_band",
    "shift_deadline",
    "taxpayer_profile_from_mapping",
]
