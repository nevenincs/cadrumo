"""Typed DTOs for the overview calendar read model.

The models separate legal obligation rows
(:class:`OverviewCalendarEntry`), observed local events
(:class:`OverviewCalendarEvent`), and filing evidence
(:class:`OverviewCalendarFilingEvidence`). Filing evidence keeps
:class:`OverviewLocalFilingState` distinct from
:class:`OverviewAeatSubmissionState` so local readiness, AEAT submission,
and justificante verification remain auditable independent axes.

These DTOs are consumed by :func:`application.overview.build_overview_calendar`
and serialized by the overview CLI payload layer. Period-bearing models hydrate
serialized :class:`~core.Period` values back into typed periods so merge
keys stay aligned with the registry-token authority.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Protocol, Self, cast

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import ElidedProse
from ...core import NotificacionEstadoServicio as _NotificacionEstadoServicio
from ...core import Period as _Period
from ...core import PostFilingEventKind as _PostFilingEventKind
from ...core.filing_year import FilingYear
from ...core.identity import AeatCsv, CalculationRevisionId, FilingRecordId, SnapshotId, WorkUnitId
from ...core.time import validate_inclusive_date_range as _validate_inclusive_date_range
from ...domain.calculations.registry.applicability import ApplicabilityVerdict
from ...domain.calculations.registry.ids import RevisionId
from ...domain.deadlines.festivos import HolidayJurisdiction as _HolidayJurisdiction
from ...domain.deadlines.models import ObligationStatus as _ObligationStatus
from ...domain.deadlines.models import Recovery as _Recovery
from ..operator_actions import DeclaredNextAction
from .coverage import ObligationCoverageReport


def _hydrate_calendar_period(value: object) -> object:
    """Hydrate a calendar JSON period string into :class:`~core.Period`."""
    if isinstance(value, str):
        return _Period.from_string(value)
    return value


def _serialize_calendar_period(value: _Period) -> str:
    """Render a typed calendar period for JSON serialization."""
    return str(value)


_CalendarPeriod = Annotated[
    _Period,
    BeforeValidator(_hydrate_calendar_period),
    PlainSerializer(_serialize_calendar_period, return_type=str),
]


class OverviewPeriodState(StrEnum):
    """Closed user-facing state derived from deadline obligation status."""

    DUE = "due"
    LATE = "late"
    FILED = "filed"
    UNKNOWN = "unknown"


class OverviewCensoEnrolmentState(StrEnum):
    """Live Modelo 036 / censo provenance state for one calendar obligation."""

    NOT_CHECKED = "not_checked"
    NOT_REQUIRED = "not_required"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class OverviewCalendarEntrySource(StrEnum):
    """Origin of one overview calendar row."""

    REGISTRY_DEADLINE = "registry_deadline"
    LOCAL_WORK_UNIT = "local_work_unit"


class OverviewLocalFilingState(StrEnum):
    """Local application-side filing axis for one calendar obligation.

    These values describe the application's internal filing lifecycle only.
    They are intentionally separate from :class:`OverviewAeatSubmissionState`
    so a ready or imported local record cannot imply official AEAT submission.
    """

    NOT_READY_TO_FILE = "not_ready_to_file"
    READY_TO_FILE = "ready_to_file"
    EXTERNAL_BASELINE_IMPORTED = "external_baseline_imported"


class OverviewAeatSubmissionState(StrEnum):
    """Observed AEAT-side submission evidence for one calendar obligation.

    :attr:`OverviewAeatSubmissionState.NOT_OBSERVED` is the default until
    already-loaded official evidence proves a submitted, accepted, or
    justificante-verified state. Overview calendar commands never create this
    evidence by contacting AEAT.
    """

    NOT_OBSERVED = "not_observed"
    SUBMITTED_OBSERVED = "submitted_observed"
    ACCEPTED = "accepted"
    JUSTIFICANTE_VERIFIED = "justificante_verified"


_USER_STATE_FOR_OBLIGATION_STATUS: MappingProxyType[_ObligationStatus, OverviewPeriodState] = MappingProxyType(
    {
        _ObligationStatus.UPCOMING: OverviewPeriodState.DUE,
        _ObligationStatus.DUE_SOON: OverviewPeriodState.DUE,
        _ObligationStatus.DUE_TODAY: OverviewPeriodState.DUE,
        _ObligationStatus.OVERDUE: OverviewPeriodState.LATE,
        _ObligationStatus.FILED: OverviewPeriodState.FILED,
        _ObligationStatus.NOT_APPLICABLE: OverviewPeriodState.UNKNOWN,
    },
)


def user_state_for(obligation_status: _ObligationStatus) -> OverviewPeriodState:
    """Return the :class:`OverviewPeriodState` for a deadline engine status."""
    return _USER_STATE_FOR_OBLIGATION_STATUS[obligation_status]


class _CalendarJustificanteStateCarrier(Protocol):
    """Fields governed by the calendar justificante evidence invariant."""

    aeat_submission_state: OverviewAeatSubmissionState | None
    justificante_verified: bool | None
    verified_justificante_csv: AeatCsv | None


class _CalendarJustificanteStateInvariant(BaseModel):
    """Enforce the shared AEAT submission and justificante evidence invariant."""

    @model_validator(mode="after")
    def _enforce_justificante_state_consistency(self) -> Self:
        value = cast(_CalendarJustificanteStateCarrier, self)
        if value.aeat_submission_state is None and value.justificante_verified is None:
            return self
        if value.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED:
            if value.justificante_verified is not True:
                raise ValueError(
                    "justificante_verified must be true when aeat_submission_state is justificante_verified",
                )
            if value.verified_justificante_csv is None:
                raise ValueError(
                    "verified_justificante_csv is required when justificante_verified is true",
                )
            return self
        if value.justificante_verified is True:
            raise ValueError(
                "justificante_verified cannot be true unless aeat_submission_state is justificante_verified",
            )
        if value.verified_justificante_csv is not None:
            raise ValueError(
                "verified_justificante_csv cannot be set unless aeat_submission_state is justificante_verified",
            )
        return self


class OverviewCalendarRange(BaseModel):
    """Inclusive date window for the ``overview calendar`` query.

    :func:`application.overview.build_overview_calendar` expands the
    window to the covered filing years and filters legal obligation rows back to
    this inclusive range.
    """

    model_config = _STRICT_FROZEN

    from_date: date
    to_date: date

    @model_validator(mode="after")
    def _enforce_window_order(self) -> OverviewCalendarRange:
        _validate_inclusive_date_range(self.from_date, self.to_date)
        return self

    def covered_years(self) -> tuple[int, ...]:
        """Every filing year this range can touch, including the prior one.

        The year before the range start is included because a filing window
        opens in the year after the period it covers.
        """
        earliest = self.from_date.year - 1
        return tuple(range(earliest, self.to_date.year + 1))

    def covers(self, candidate: date) -> bool:
        """Whether *candidate* falls inside this range, both ends included."""
        return self.from_date <= candidate <= self.to_date


class OverviewCalendarFilingEvidence(_CalendarJustificanteStateInvariant):
    """Filing evidence attached to one legal calendar obligation.

    The local fields describe the application's filing-record axis; the
    AEAT fields describe observed submission evidence from persisted official
    sources. Validators require ``justificante_verified`` and
    ``verified_justificante_csv`` to agree exactly with
    :attr:`OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED`, preventing a
    malformed event from claiming receipt verification without CSV evidence.
    """

    model_config = _STRICT_FROZEN

    modelo: str | None = Field(default=None, min_length=1, max_length=8)
    filing_year: FilingYear | None = None
    period: _CalendarPeriod | None = None
    local_filing_state: OverviewLocalFilingState = OverviewLocalFilingState.NOT_READY_TO_FILE
    local_filing_record_id: FilingRecordId | None = None
    local_calculation_revision_id: CalculationRevisionId | None = None
    local_filed_at: datetime | None = None
    aeat_submission_state: OverviewAeatSubmissionState = OverviewAeatSubmissionState.NOT_OBSERVED
    aeat_submitted_at: datetime | None = None
    aeat_reference_id: str | None = Field(default=None, min_length=1, max_length=128)
    aeat_snapshot_id: SnapshotId | None = None
    aeat_evidence_kind: str | None = Field(default=None, min_length=1, max_length=64)
    aeat_evidence_conflict_reference_ids: tuple[str, ...] = Field(default_factory=tuple)
    verified_justificante_csv: AeatCsv | None = None
    justificante_required: bool = True
    justificante_verified: bool = False
    evidence_source: str | None = Field(default=None, min_length=1, max_length=64)


class OverviewCalendarEntry(BaseModel):
    """One legal ``(modelo, period)`` row in the calendar view.

    The deadline fields mirror :class:`~domain.deadlines.ModeloDeadline`.
    The optional :class:`OverviewCalendarFilingEvidence` row attaches local and
    AEAT evidence without changing the legal deadline status from the deadline
    engine.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: _CalendarPeriod
    opens_on: date
    closes_on: date
    adjusted_closes_on: date
    shift_reason: str = Field(min_length=1, max_length=64)
    holiday_refs: tuple[str, ...] = Field(default_factory=tuple)
    jurisdictions: tuple[_HolidayJurisdiction, ...] = Field(default_factory=tuple)
    payment_cutoff_on: date | None = None
    status: _ObligationStatus
    user_state: OverviewPeriodState
    recovery: _Recovery | None = None
    recovery_action: DeclaredNextAction | None = Field(default=None, exclude=True)
    filing_year: FilingYear | None = None
    censo_enrolment_state: OverviewCensoEnrolmentState = OverviewCensoEnrolmentState.NOT_CHECKED
    filing_evidence: OverviewCalendarFilingEvidence = Field(default_factory=lambda: OverviewCalendarFilingEvidence())
    source: OverviewCalendarEntrySource = OverviewCalendarEntrySource.REGISTRY_DEADLINE
    local_work_unit_id: WorkUnitId | None = None
    local_work_unit_name: str | None = Field(default=None, min_length=1, max_length=200)
    local_work_unit_revision_id: RevisionId | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def _enforce_window_order(self) -> OverviewCalendarEntry:
        if self.opens_on > self.closes_on:
            raise ValueError(f"OverviewCalendarEntry.opens_on ({self.opens_on}) is after closes_on ({self.closes_on})")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise ValueError(
                f"OverviewCalendarEntry.payment_cutoff_on ({self.payment_cutoff_on}) "
                f"is after closes_on ({self.closes_on})",
            )
        if self.adjusted_closes_on < self.closes_on:
            raise ValueError(
                f"OverviewCalendarEntry.adjusted_closes_on ({self.adjusted_closes_on}) "
                f"precedes closes_on ({self.closes_on}); the shift rule may only move "
                f"a deadline forward.",
            )
        return self

    @model_validator(mode="after")
    def _enforce_user_state_consistency(self) -> OverviewCalendarEntry:
        expected = _USER_STATE_FOR_OBLIGATION_STATUS[self.status]
        if self.user_state is not expected:
            raise ValueError(
                f"OverviewCalendarEntry.user_state ({self.user_state}) "
                f"disagrees with engine status mapping ({expected})",
            )
        return self

    @model_validator(mode="after")
    def _enforce_recovery_action_consistency(self) -> OverviewCalendarEntry:
        if (self.recovery is None) != (self.recovery_action is None):
            raise ValueError("OverviewCalendarEntry recovery and recovery_action must be present together")
        return self


class OverviewCalendarEventType(StrEnum):
    """Observed event categories shown alongside legal filing windows."""

    FILING = "filing"
    MESSAGE = "message"


#: The calendar-event ``summary`` annotation: elides rather than refusing.
#:
#: Built by interpolating a modelo label and its period into a sentence, so an
#: unusually long obligation label is enough to cross the cap. Refusing would
#: fail the whole calendar read over one event's wording.
_EventSummary = Annotated[str, ElidedProse(256)]


class OverviewCalendarEvent(_CalendarJustificanteStateInvariant):
    """One observed local event attached to an overview calendar range.

    Filing events may carry :class:`OverviewAeatSubmissionState` when a
    persisted snapshot already observed it. Messages and unverified filings
    remain event-only observations and do not imply
    :class:`OverviewCalendarFilingEvidence` or receipt verification.

    ``post_filing_kind`` carries the fine-grained
    :class:`~core.PostFilingEventKind` procedural category (requerimiento,
    propuesta de liquidación, diligencia de embargo, …) classified from the
    pulled notification / expediente, so the coarse ``event_type`` axis does not
    collapse a demand for documents and an informational comunicación onto the
    same ``message`` row.

    ``notificacion_estado_servicio`` carries the orthogonal
    :class:`~core.NotificacionEstadoServicio` service state — whether the
    notification is still inside its Ley 39/2015 art. 43.2 window, was accessed,
    or has lapsed into rechazo tácito and is therefore legally served. It is
    populated only for ``message`` rows projected from notification snapshots,
    where a ``fecha de notificación`` and an access flag exist to compute it
    from; every other event source leaves it ``None``.
    """

    model_config = _STRICT_FROZEN

    event_type: OverviewCalendarEventType
    post_filing_kind: _PostFilingEventKind | None = None
    notificacion_estado_servicio: _NotificacionEstadoServicio | None = None
    event_date: date
    source: str = Field(min_length=1, max_length=64)
    summary: _EventSummary
    reference_id: str = Field(min_length=1, max_length=128)
    snapshot_id: SnapshotId | None = None
    modelo: str | None = Field(default=None, min_length=1, max_length=8)
    filing_year: FilingYear | None = None
    period: _CalendarPeriod | None = None
    status: str | None = Field(default=None, max_length=64)
    source_url: str | None = Field(default=None, max_length=512)
    authenticated_identity: str | None = Field(default=None, max_length=32, exclude=True)
    aeat_submission_state: OverviewAeatSubmissionState | None = None
    aeat_submitted_at: datetime | None = None
    justificante_verified: bool | None = None
    verified_justificante_csv: AeatCsv | None = None

    @model_validator(mode="after")
    def _enforce_notification_service_state_on_message_events(self) -> OverviewCalendarEvent:
        """Reject a notification service state attached to a non-message event."""
        if self.notificacion_estado_servicio is not None and self.event_type is not OverviewCalendarEventType.MESSAGE:
            raise ValueError("notificacion_estado_servicio may only be set on message events")
        return self


class CalendarWarning(BaseModel):
    """One under-specified-profile warning attached to a calendar query.

    Attributes:
        code: Stable warning identity; for a profile-completeness gap this is
            the profile field's declared selector token.
        message: Locale key for the operator-facing explanation.
        fix_action: The catalogue action that answers this warning. It carries
            no command string and no CLI path: resolution against the live
            command surface belongs to the presentation boundary, which projects
            the resolved form onto this warning's envelope notice.

            It is excluded from serialization deliberately. An unresolved
            declaration on the wire would be a second, weaker statement of the
            same remedy the notice already carries fully resolved, and a remedy
            field inside a result payload is the shape the envelope contract
            reserves for the notice channel.
        affected_modelos: Obligation rows this gap can distort.
    """

    model_config = _STRICT_FROZEN

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=128)
    fix_action: DeclaredNextAction = Field(exclude=True)
    affected_modelos: tuple[str, ...] = Field(default=())


class CalendarCompleteness(BaseModel):
    """Breakdown of explicit profile values versus deadline-engine defaults."""

    model_config = _STRICT_FROZEN

    explicitly_set_keys: tuple[str, ...] = Field(default=())
    defaulted_keys: tuple[str, ...] = Field(default=())
    computable_modelos: tuple[str, ...] = Field(default=())
    defaulted_modelos: tuple[str, ...] = Field(default=())


class SuppressedCalendarEntry(BaseModel):
    """One non-applicable obligation retained by ``--show-suppressed``."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: _CalendarPeriod
    verdict: ApplicabilityVerdict
    reason: str = Field(min_length=1)


class OverviewCalendar(BaseModel):
    """Result of an ``aeat app overview calendar`` query.

    ``entries`` contains legal filing windows, ``events`` contains additive
    local observations, and ``suppressed_entries`` preserves filtered
    applicability rows only when the caller explicitly requests them.
    ``coverage`` is the always-populated reconciliation of the full registry
    modelo set against ``entries``: its ``advised`` bucket names every filing
    obligation the surface would otherwise have silently dropped, so a machine
    consumer never has to infer coverage from the presence or absence of a row.
    """

    model_config = _STRICT_FROZEN

    range: OverviewCalendarRange
    entries: tuple[OverviewCalendarEntry, ...]
    generated_at: datetime
    warnings: tuple[CalendarWarning, ...] = Field(default=())
    completeness: CalendarCompleteness = Field(default_factory=CalendarCompleteness)
    taxpayer_model_declared: bool = True
    incomplete_reason: str | None = None
    suppressed_entries: tuple[SuppressedCalendarEntry, ...] = Field(default=())
    events: tuple[OverviewCalendarEvent, ...] = Field(default=())
    coverage: ObligationCoverageReport = Field(default_factory=ObligationCoverageReport)


class OverviewStatusReport(BaseModel):
    """Current active-profile readiness counters for ``overview status``.

    Produced from :class:`~application.state_projection.OperatorStateProjection`
    by :func:`application.overview.overview_status_report_from_projection`.
    """

    model_config = _STRICT_FROZEN

    active_profile_name: str | None = None
    transactions: int = Field(ge=0)
    invoices: int = Field(ge=0)
    drafts: int = Field(ge=0)
    work_units: int = Field(default=0, ge=0)
    discarded_work_units: int = Field(default=0, ge=0)
    calculation_revisions: int = Field(default=0, ge=0)
    unreadable_rows: int = Field(ge=0)
    filing_obligation_advisories: tuple[str, ...] = Field(default=())
    unsupported_work_create_modelos: tuple[str, ...] = Field(default=())


__all__ = [
    "CalendarCompleteness",
    "CalendarWarning",
    "OverviewAeatSubmissionState",
    "OverviewCalendar",
    "OverviewCalendarEntry",
    "OverviewCalendarEntrySource",
    "OverviewCalendarEvent",
    "OverviewCalendarEventType",
    "OverviewCalendarFilingEvidence",
    "OverviewCalendarRange",
    "OverviewCensoEnrolmentState",
    "OverviewLocalFilingState",
    "OverviewPeriodState",
    "OverviewStatusReport",
    "SuppressedCalendarEntry",
    "user_state_for",
]
