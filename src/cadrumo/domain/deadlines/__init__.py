"""Public facade for registry-backed filing deadline computation.

:class:`DeadlineEngine` is the project's first user-visible
"answer-the-user" surface: given an :class:`TaxpayerProfile` and a
year, it produces a deterministic typed :class:`Schedule` of every
filing the taxpayer profile is obliged to submit, with concrete
opens / closes dates and a current :class:`ObligationStatus`. Each
:class:`ModeloDeadline` may also carry a :class:`Recovery` payload backed by
the Ley 58/2003 art. 27 :class:`RecargoBand` table when the obligation is
overdue.

The engine is read-only — it never touches the storage layer, never
files anything, and never mutates its inputs.

The facade also exposes the taxpayer-shape enums consumed by registry
applicability predicates (:class:`EntityType`, :class:`LegalEntityForm`,
:class:`IrpfIncomeCategory`, :class:`IrpfEstimationRegime`,
:class:`FiscalResidency`) and the BOE-cited holiday shift substrate
(:class:`CalendarCCAA`, :class:`HolidayCalendar`, :class:`DeadlineShift`,
:func:`shift_deadline`, :data:`MODELOS_WITHOUT_SHIFT`). Profile mappings enter
through :func:`taxpayer_profile_from_mapping`; local overview and workflow
services consume the resulting :class:`Schedule` rather than rebuilding deadline
or recovery logic.

See Also:
    :class:`domain.calculations.registry.ValidatedRegistryAuthority`
        Registry authority that supplies modelo deadline windows and
        applicability predicates consumed by :class:`DeadlineEngine`.
    :func:`compute_obligation_schedule`
        Single producer used by workflow gates and state projections to avoid
        divergent pending-obligation calculations.
    :func:`taxpayer_profile_from_mapping`
        Profile-value mapper used by application profile projections before
        calling this domain engine.
    :mod:`application.workflow`
        Application workflow gate that evaluates deadline obligations before
        verification and local filing steps.
    :mod:`application.overview`
        Local overview read model that merges this schedule with stored filing
        evidence.

Examples:
    >>> from datetime import date
    >>> from cadrumo.domain.deadlines import (
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
    classify_obligation_status,
    compute_obligation_schedule,
    explain,
    next_deadline,
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
    ChargeAccount,
    CrossPeriodGroupMemberRoster,
    EntityType,
    FiscalResidency,
    IrpfActivityKind,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    LegalEntityForm,
    M303RegimeComposition,
    M303TaxTerritory,
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
    resolve_multiple_pagadores_reduced_limit,
)
from ._plazo import resolve_filing_closes_on, resolve_filing_window
from ._profiles import (
    MODELO_IVA_BLOCK_CLAIMING_PATHS,
    MODELO_IVA_BLOCK_REQUIRED_PATHS,
    modelo_iva_profile_required_paths,
    profile_claims_modelo_iva_block,
    taxpayer_profile_from_mapping,
)
from ._recargo import (
    build_recovery_for_overdue,
    completed_months_late,
    load_recargo_bands,
    resolve_recargo_band,
    twelve_month_anniversary,
)
from .errors import (
    DeadlineError,
    DeadlineValidationError,
    NoDeadlineWindowsError,
    ProfileError,
    ScheduleComputationError,
)

__all__ = [
    "MODELOS_WITHOUT_SHIFT",
    "MODELO_IVA_BLOCK_CLAIMING_PATHS",
    "MODELO_IVA_BLOCK_REQUIRED_PATHS",
    "CalendarCCAA",
    "ChargeAccount",
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
    "IrpfActivityKind",
    "IrpfEstimationRegime",
    "IrpfIncomeCategory",
    "IrpfSpecialRegime",
    "LegalEntityForm",
    "M303RegimeComposition",
    "M303TaxTerritory",
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
    "classify_obligation_status",
    "completed_months_late",
    "compute_obligation_schedule",
    "evaluate_multiple_pagadores_obligation",
    "explain",
    "irnr_representante_fiscal_required",
    "is_business_day",
    "is_ue_eee_country_code",
    "load_holiday_calendar",
    "load_recargo_bands",
    "modelo_iva_profile_required_paths",
    "next_business_day",
    "next_deadline",
    "profile_claims_modelo_iva_block",
    "resolve_filing_closes_on",
    "resolve_filing_window",
    "resolve_multiple_pagadores_reduced_limit",
    "resolve_recargo_band",
    "shift_deadline",
    "taxpayer_profile_from_mapping",
    "twelve_month_anniversary",
]
