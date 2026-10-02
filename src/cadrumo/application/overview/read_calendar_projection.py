"""Closed snapshots for calendar-derived overview reads."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.filing_year import FilingYear
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, SnapshotId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.notificacion_estado_servicio import NotificacionEstadoServicio
from ...core.period import Period
from ...core.post_filing_event import PostFilingEventKind
from ...domain.calculations.registry.applicability import ApplicabilityVerdict
from ...domain.deadlines.festivos import DeadlineHolidayCoverage, HolidayJurisdiction
from ...domain.deadlines.models import ObligationStatus, RecargoBand, Recovery
from ..operations.public_scalar import PublicDecimal
from .agenda import OverviewAgenda
from .backlog import OverviewBacklog
from .calendar_models import (
    CalendarCompleteness,
    CalendarWarning,
    OverviewAeatSubmissionState,
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEntrySource,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewCensoEnrolmentState,
    OverviewLocalFilingState,
    OverviewPeriodState,
    SuppressedCalendarEntry,
)
from .coverage import ObligationCoverageReport
from .pipeline_projection import PipelineNextActionSnapshot


def _period(value: str) -> Period:
    return Period.from_string(value)


class OverviewFilingEvidenceSnapshot(BaseModel):
    """Filing axes without raw identity or custom period serialization."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str | None = None
    filing_year: FilingYear | None = None
    period: str | None = None
    local_filing_state: OverviewLocalFilingState
    local_filing_record_id: FilingRecordId | None = None
    local_calculation_revision_id: CalculationRevisionId | None = None
    local_filed_at: datetime | None = None
    aeat_submission_state: OverviewAeatSubmissionState
    aeat_submitted_at: datetime | None = None
    aeat_reference_id: str | None = None
    aeat_snapshot_id: SnapshotId | None = None
    aeat_evidence_kind: str | None = None
    aeat_evidence_conflict_reference_ids: tuple[str, ...] = ()
    verified_justificante_csv: str | None = None
    justificante_required: bool
    justificante_verified: bool
    evidence_source: str | None = None

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_evidence()
        return self

    @classmethod
    def from_evidence(cls, value: OverviewCalendarFilingEvidence) -> Self:
        """Copy the canonical evidence axes without a whole aggregate."""
        return cls.model_validate(
            value.model_dump(mode="python", exclude={"period"})
            | {"period": str(value.period) if value.period else None}
        )

    def to_evidence(self) -> OverviewCalendarFilingEvidence:
        """Revalidate the filing evidence against canonical invariants."""
        return OverviewCalendarFilingEvidence.model_validate(
            self.model_dump(mode="python", exclude={"period"})
            | {"period": _period(self.period) if self.period else None}
        )


class OverviewRecoveryBandSnapshot(BaseModel):
    """The displayed statutory recargo band, with canonical decimal text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    id: str
    min_completed_months: NonNegativeInt
    max_completed_months: int | None
    surcharge_pct: PublicDecimal
    interest_applies: bool
    legal_ref: str

    @classmethod
    def from_band(cls, value: RecargoBand) -> Self:
        """Copy only the established recargo band fields."""
        return cls(
            id=value.id,
            min_completed_months=value.min_completed_months,
            max_completed_months=value.max_completed_months,
            surcharge_pct=PublicDecimal(decimal=str(value.surcharge_pct)),
            interest_applies=value.interest_applies,
            legal_ref=value.legal_ref,
        )

    def to_band(self) -> RecargoBand:
        """Restore canonical band validation for existing readback rendering."""
        return RecargoBand(
            id=self.id,
            min_completed_months=self.min_completed_months,
            max_completed_months=self.max_completed_months,
            surcharge_pct=Decimal(self.surcharge_pct.decimal),
            interest_applies=self.interest_applies,
            legal_ref=self.legal_ref,
        )


class OverviewRecoverySnapshot(BaseModel):
    """Read-only statutory recovery fact, without execution capability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    still_filable: bool
    recargo_band: OverviewRecoveryBandSnapshot

    @classmethod
    def from_recovery(cls, value: Recovery) -> Self:
        """Capture the existing statutory recovery annotation."""
        return cls(
            still_filable=value.still_filable, recargo_band=OverviewRecoveryBandSnapshot.from_band(value.recargo_band)
        )

    def to_recovery(self) -> Recovery:
        """Restore the canonical annotation for existing text rendering."""
        return Recovery(still_filable=self.still_filable, recargo_band=self.recargo_band.to_band())


class OverviewCalendarEntrySnapshot(BaseModel):
    """One validated deadline row and its already-derived local observations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    period: str
    opens_on: date
    closes_on: date
    adjusted_closes_on: date
    shift_reason: str
    holiday_refs: tuple[str, ...]
    jurisdictions: tuple[HolidayJurisdiction, ...]
    holiday_coverage: DeadlineHolidayCoverage
    holiday_territory: str | None
    payment_cutoff_on: date | None
    evaluated_on: date
    days_overdue: NonNegativeInt | None
    status: ObligationStatus
    user_state: OverviewPeriodState
    recovery: OverviewRecoverySnapshot | None
    recovery_action: PipelineNextActionSnapshot | None
    filing_year: FilingYear | None
    censo_enrolment_state: OverviewCensoEnrolmentState
    filing_evidence: OverviewFilingEvidenceSnapshot
    source: OverviewCalendarEntrySource
    local_work_unit_id: WorkUnitId | None
    local_work_unit_name: str | None
    local_work_unit_revision_id: str | None

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_entry()
        return self

    @classmethod
    def from_entry(cls, value: OverviewCalendarEntry) -> Self:
        """Copy the canonical row while replacing its custom period and actions."""
        data = value.model_dump(mode="python", exclude={"period", "filing_evidence", "recovery", "recovery_action"})
        return cls.model_validate(
            data
            | {
                "period": str(value.period),
                "filing_evidence": OverviewFilingEvidenceSnapshot.from_evidence(value.filing_evidence),
                "recovery": OverviewRecoverySnapshot.from_recovery(value.recovery) if value.recovery else None,
                "recovery_action": PipelineNextActionSnapshot.from_action(value.recovery_action)
                if value.recovery_action
                else None,
            }
        )

    def to_entry(self) -> OverviewCalendarEntry:
        """Revalidate deadlines, user state, evidence and recovery consistency."""
        return OverviewCalendarEntry.model_validate(
            self.model_dump(mode="python", exclude={"period", "filing_evidence", "recovery", "recovery_action"})
            | {
                "period": _period(self.period),
                "filing_evidence": self.filing_evidence.to_evidence(),
                "recovery": self.recovery.to_recovery() if self.recovery else None,
                "recovery_action": self.recovery_action.to_action() if self.recovery_action else None,
            }
        )


class OverviewCalendarEventSnapshot(BaseModel):
    """Observed event fields currently emitted, excluding authenticated identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    event_type: OverviewCalendarEventType
    post_filing_kind: PostFilingEventKind | None
    notificacion_estado_servicio: NotificacionEstadoServicio | None
    event_date: date
    source: str
    summary: str
    reference_id: str
    snapshot_id: SnapshotId | None
    modelo: str | None
    filing_year: FilingYear | None
    period: str | None
    status: str | None
    source_url: str | None
    aeat_submission_state: OverviewAeatSubmissionState | None
    aeat_submitted_at: datetime | None
    justificante_verified: bool | None
    verified_justificante_csv: str | None

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_event()
        return self

    @classmethod
    def from_event(cls, value: OverviewCalendarEvent) -> Self:
        """Capture one already-projected calendar event without raw identity."""
        return cls.model_validate(
            value.model_dump(mode="python", exclude={"period", "authenticated_identity"})
            | {"period": str(value.period) if value.period else None}
        )

    def to_event(self) -> OverviewCalendarEvent:
        """Restore the canonical event and AEAT evidence invariants."""
        return OverviewCalendarEvent.model_validate(
            self.model_dump(mode="python", exclude={"period"})
            | {"period": _period(self.period) if self.period else None}
        )


class OverviewCalendarWarningSnapshot(BaseModel):
    """One grounded warning and its declared next action."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: str
    message: str
    fix_action: PipelineNextActionSnapshot
    affected_modelos: tuple[str, ...]

    @classmethod
    def from_warning(cls, value: CalendarWarning) -> Self:
        """Preserve warning grounding and canonical action."""
        return cls(
            code=value.code,
            message=value.message,
            fix_action=PipelineNextActionSnapshot.from_action(value.fix_action),
            affected_modelos=value.affected_modelos,
        )

    def to_warning(self) -> CalendarWarning:
        """Restore one canonical warning for localized output."""
        return CalendarWarning(
            code=self.code,
            message=self.message,
            fix_action=self.fix_action.to_action(),
            affected_modelos=self.affected_modelos,
        )


class OverviewSuppressedEntrySnapshot(BaseModel):
    """One explicitly requested non-applicable obligation row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    period: str
    verdict: ApplicabilityVerdict
    reason: str

    @classmethod
    def from_entry(cls, value: SuppressedCalendarEntry) -> Self:
        """Copy the registry-derived suppression verdict."""
        return cls(modelo=value.modelo, period=str(value.period), verdict=value.verdict, reason=value.reason)

    def to_entry(self) -> SuppressedCalendarEntry:
        """Revalidate the canonical suppressed obligation."""
        return SuppressedCalendarEntry(
            modelo=self.modelo, period=_period(self.period), verdict=self.verdict, reason=self.reason
        )


class OverviewCalendarSnapshot(BaseModel):
    """Full current calendar output without private input records."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    range: OverviewCalendarRange
    evaluated_on: date
    entries: tuple[OverviewCalendarEntrySnapshot, ...]
    generated_at: datetime
    warnings: tuple[OverviewCalendarWarningSnapshot, ...]
    completeness: CalendarCompleteness
    taxpayer_model_declared: bool
    incomplete_reason: str | None
    suppressed_entries: tuple[OverviewSuppressedEntrySnapshot, ...]
    events: tuple[OverviewCalendarEventSnapshot, ...]
    coverage: ObligationCoverageReport

    @classmethod
    def from_calendar(cls, value: OverviewCalendar) -> Self:
        """Copy legal rows, observed events, completeness and total coverage."""
        return cls(
            range=value.range,
            evaluated_on=value.evaluated_on,
            entries=tuple(OverviewCalendarEntrySnapshot.from_entry(row) for row in value.entries),
            generated_at=value.generated_at,
            warnings=tuple(OverviewCalendarWarningSnapshot.from_warning(row) for row in value.warnings),
            completeness=value.completeness,
            taxpayer_model_declared=value.taxpayer_model_declared,
            incomplete_reason=value.incomplete_reason,
            suppressed_entries=tuple(
                OverviewSuppressedEntrySnapshot.from_entry(row) for row in value.suppressed_entries
            ),
            events=tuple(OverviewCalendarEventSnapshot.from_event(row) for row in value.events),
            coverage=value.coverage,
        )

    def to_calendar(self) -> OverviewCalendar:
        """Reconstruct only the validated canonical calendar for presentation."""
        return OverviewCalendar(
            range=self.range,
            evaluated_on=self.evaluated_on,
            entries=tuple(row.to_entry() for row in self.entries),
            generated_at=self.generated_at,
            warnings=tuple(row.to_warning() for row in self.warnings),
            completeness=self.completeness,
            taxpayer_model_declared=self.taxpayer_model_declared,
            incomplete_reason=self.incomplete_reason,
            suppressed_entries=tuple(row.to_entry() for row in self.suppressed_entries),
            events=tuple(row.to_event() for row in self.events),
            coverage=self.coverage,
        )


class OverviewAgendaSnapshot(BaseModel):
    """Ordered agenda cohorts built by the canonical calendar service."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    as_of: date
    horizon_days: int
    next_due: OverviewCalendarEntrySnapshot | None
    due_today: tuple[OverviewCalendarEntrySnapshot, ...]
    due_soon: tuple[OverviewCalendarEntrySnapshot, ...]
    overdue: tuple[OverviewCalendarEntrySnapshot, ...]
    generated_at: datetime
    warnings: tuple[OverviewCalendarWarningSnapshot, ...]
    completeness: CalendarCompleteness
    coverage: ObligationCoverageReport
    taxpayer_model_declared: bool
    incomplete_reason: str | None

    @classmethod
    def from_agenda(cls, value: OverviewAgenda) -> Self:
        """Copy current ordered cohorts without recomputing deadlines."""
        return cls(
            as_of=value.as_of,
            horizon_days=value.horizon_days,
            next_due=OverviewCalendarEntrySnapshot.from_entry(value.next_due) if value.next_due else None,
            due_today=tuple(OverviewCalendarEntrySnapshot.from_entry(row) for row in value.due_today),
            due_soon=tuple(OverviewCalendarEntrySnapshot.from_entry(row) for row in value.due_soon),
            overdue=tuple(OverviewCalendarEntrySnapshot.from_entry(row) for row in value.overdue),
            generated_at=value.generated_at,
            warnings=tuple(OverviewCalendarWarningSnapshot.from_warning(row) for row in value.warnings),
            completeness=value.completeness,
            coverage=value.coverage,
            taxpayer_model_declared=value.taxpayer_model_declared,
            incomplete_reason=value.incomplete_reason,
        )

    def to_agenda(self) -> OverviewAgenda:
        """Restore the captured canonical cohorts for localized CLI output."""
        return OverviewAgenda(
            as_of=self.as_of,
            horizon_days=self.horizon_days,
            next_due=self.next_due.to_entry() if self.next_due else None,
            due_today=tuple(row.to_entry() for row in self.due_today),
            due_soon=tuple(row.to_entry() for row in self.due_soon),
            overdue=tuple(row.to_entry() for row in self.overdue),
            generated_at=self.generated_at,
            warnings=tuple(row.to_warning() for row in self.warnings),
            completeness=self.completeness,
            coverage=self.coverage,
            taxpayer_model_declared=self.taxpayer_model_declared,
            incomplete_reason=self.incomplete_reason,
        )


class OverviewBacklogSnapshot(BaseModel):
    """Canonical past-due cohort with its exact calendar window."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    range: OverviewCalendarRange
    as_of: date
    items: tuple[OverviewCalendarEntrySnapshot, ...]
    late_count: NonNegativeInt
    generated_at: datetime
    warnings: tuple[OverviewCalendarWarningSnapshot, ...]
    completeness: CalendarCompleteness
    coverage: ObligationCoverageReport
    taxpayer_model_declared: bool
    incomplete_reason: str | None

    @classmethod
    def from_backlog(cls, value: OverviewBacklog) -> Self:
        """Preserve ordered late rows and total coverage without a new filter."""
        return cls(
            range=value.range,
            as_of=value.as_of,
            items=tuple(OverviewCalendarEntrySnapshot.from_entry(row) for row in value.items),
            late_count=value.late_count,
            generated_at=value.generated_at,
            warnings=tuple(OverviewCalendarWarningSnapshot.from_warning(row) for row in value.warnings),
            completeness=value.completeness,
            coverage=value.coverage,
            taxpayer_model_declared=value.taxpayer_model_declared,
            incomplete_reason=value.incomplete_reason,
        )

    def to_backlog(self) -> OverviewBacklog:
        """Restore the validated canonical backlog for existing rendering."""
        return OverviewBacklog(
            range=self.range,
            as_of=self.as_of,
            items=tuple(row.to_entry() for row in self.items),
            late_count=self.late_count,
            generated_at=self.generated_at,
            warnings=tuple(row.to_warning() for row in self.warnings),
            completeness=self.completeness,
            coverage=self.coverage,
            taxpayer_model_declared=self.taxpayer_model_declared,
            incomplete_reason=self.incomplete_reason,
        )


__all__ = ["OverviewAgendaSnapshot", "OverviewBacklogSnapshot", "OverviewCalendarSnapshot"]
