"""Validated item snapshots used by overview calendar projections."""

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
from .calendar_models import (
    CalendarWarning,
    OverviewAeatEvidenceConcern,
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarEntrySource,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewCensoEnrolmentState,
    OverviewLocalFilingState,
    OverviewPeriodState,
    SuppressedCalendarEntry,
)
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
    aeat_evidence_concerns: tuple[OverviewAeatEvidenceConcern, ...] = ()
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


__all__ = [
    "OverviewCalendarEntrySnapshot",
    "OverviewCalendarEventSnapshot",
    "OverviewCalendarWarningSnapshot",
    "OverviewFilingEvidenceSnapshot",
    "OverviewRecoveryBandSnapshot",
    "OverviewRecoverySnapshot",
    "OverviewSuppressedEntrySnapshot",
]
