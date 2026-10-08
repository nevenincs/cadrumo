"""Immutable synthetic portfolio states for reviewing the shipped filing UI.

These are visual fixtures, not proof of calculation or installed persistence.
They hand the production screens typed application projections; the installed
creation and AEAT-reader tests own that evidence. No fixture writes tax data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.application.modelo.declaration_summary import DeclarationSummary, DeclarationSummaryState
from cadrumo.application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from cadrumo.application.modelo.declarations_workspace_contracts import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)
from cadrumo.application.modelo.work_form_models import ModeloFormResult, ModeloFormResultDirection
from cadrumo.application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntrySource,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from cadrumo.application.overview.coverage import AdvisedObligation, CoverageAdviceReason, ObligationCoverageReport
from cadrumo.application.overview.home import HomeAvailability
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.deadlines.festivos import DeadlineHolidayCoverage
from cadrumo.domain.deadlines.models import ObligationStatus
from cadrumo.domain.modelos.work_unit import WorkUnitState

_NOW = datetime(2025, 4, 30, 12, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")
_NEXT = Period.from_year_and_code(2025, "2T")
_BUCKET = "13000000-0000-4000-8000-000000000890"


def portfolio_projection() -> tuple[DeclarationsWorkspaceProjectionV1, DeclarationsCalendarProjectionV1]:
    """Supply every filing group, plus a local draft beside an external ALTA."""
    definitions = (
        ("a", "130", DeclarationSummaryState.BLOCKED, "300", ModeloFormResultDirection.TO_PAY, False),
        ("b", "303", DeclarationSummaryState.CALCULATED, None, ModeloFormResultDirection.UNKNOWN, False),
        ("c", "111", DeclarationSummaryState.CHECKED, "0", ModeloFormResultDirection.NIL, False),
        ("d", "115", DeclarationSummaryState.RECORDED, "240", ModeloFormResultDirection.TO_PAY, False),
    )
    declarations = tuple(
        DeclarationsWorkspaceDeclarationRefV1(
            work_unit_id=digit * 64,
            modelo=modelo,
            filing_year=2025,
            period=_PERIOD,
            state=WorkUnitState.BORRADOR,
            has_current_calculation=True,
            has_current_filing=state is DeclarationSummaryState.RECORDED,
            summary=DeclarationSummary(
                state=state,
                checked=state in {DeclarationSummaryState.CHECKED, DeclarationSummaryState.RECORDED},
                blocking_count=2 if state is DeclarationSummaryState.BLOCKED else 0,
                result=None
                if value is None
                else ModeloFormResult(
                    casilla_id=validated_casilla_id("01"),
                    box="01",
                    value=Decimal(value),
                    direction=direction,
                ),
                is_correction=correction,
            ),
        )
        for digit, modelo, state, value, direction, correction in definitions
    )
    workspace = DeclarationsWorkspaceProjectionV1(
        bucket_id=_BUCKET,
        zones=tuple(
            DeclarationsWorkspaceZoneStateV1(
                zone=zone,
                availability=DeclarationsWorkspaceAvailability.AVAILABLE,
                observed_at=_NOW,
                sources=tuple(DeclarationsWorkspaceSource),
                item_count=len(declarations) if zone is DeclarationsWorkspaceZone.DECLARATIONS else 0,
            )
            for zone in DeclarationsWorkspaceZone
        ),
        declarations=declarations,
        calculation_revisions=(),
        filings=(),
        lifecycle=(),
    )
    entries = (
        _calendar_entry("303", _PERIOD, date(2025, 4, 21), external=True),
        _calendar_entry("349", _NEXT, date(2025, 7, 21)),
        _calendar_entry("390", Period.from_year_and_code(2024, "0A"), date(2025, 1, 30), concern=True),
    )
    calendar = DeclarationsCalendarProjectionV1(
        as_of=_NOW.date(),
        generated_at=_NOW,
        query_range=OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31)),
        sources=tuple(
            DeclarationsCalendarSourceStateV1(
                source=source,
                availability=HomeAvailability.AVAILABLE,
                observed_at=_NOW,
                item_count=len(entries),
            )
            for source in DeclarationsCalendarSource
        ),
        entries=entries,
        coverage=ObligationCoverageReport(
            advised=(AdvisedObligation(modelo="100", reason=CoverageAdviceReason.APPLICABILITY_UNDETERMINED),)
        ),
    )
    return workspace, calendar


def _calendar_entry(
    modelo: str, period: Period, closes: date, *, external: bool = False, concern: bool = False
) -> DeclarationsCalendarEntryRefV1:
    overdue = closes < _NOW.date() and not external
    return DeclarationsCalendarEntryRefV1(
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        opens_on=closes.replace(day=1),
        closes_on=closes,
        adjusted_closes_on=closes,
        shift_reason="unchanged",
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        evaluated_on=_NOW.date(),
        days_overdue=(_NOW.date() - closes).days if overdue else None,
        legal_status=ObligationStatus.FILED
        if external
        else ObligationStatus.OVERDUE
        if overdue
        else ObligationStatus.UPCOMING,
        user_state=OverviewPeriodState.FILED
        if external
        else OverviewPeriodState.LATE
        if overdue
        else OverviewPeriodState.DUE,
        local_filing_state=OverviewLocalFilingState.NOT_READY_TO_FILE,
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        if external
        else OverviewAeatSubmissionState.NOT_OBSERVED,
        aeat_submitted_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC) if external else None,
        aeat_reference_id="20250000000000000001" if external else None,
        aeat_needs_check=concern,
        justificante_verified=False,
        evidence_conflicted=False,
        source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
    )
