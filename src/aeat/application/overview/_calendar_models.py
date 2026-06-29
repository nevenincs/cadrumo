"""Typed DTOs for the overview calendar read model.

The models separate legal obligation rows
(:class:`OverviewCalendarEntry`), observed local events
(:class:`OverviewCalendarEvent`), and filing evidence
(:class:`OverviewCalendarFilingEvidence`). Filing evidence keeps
:class:`OverviewLocalFilingState` distinct from
:class:`OverviewAeatSubmissionState` so local readiness, AEAT submission,
and justificante verification remain auditable independent axes.

These DTOs are consumed by :func:`aeat.application.overview.build_overview_calendar`
and serialized by the overview CLI payload layer. Period-bearing models hydrate
serialized :class:`~aeat.core.Period` values back into typed periods so merge
keys stay aligned with the registry-token authority.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period as _Period
from ...domain.calculations.registry.applicability import ApplicabilityVerdict
from ...domain.deadlines import HolidayJurisdiction as _HolidayJurisdiction
from ...domain.deadlines import ObligationStatus as _ObligationStatus
from ...domain.deadlines import Recovery as _Recovery


def _period_from_serialized(value: object) -> object:
    """Hydrate overview JSON period strings into :class:`~aeat.core.Period`."""
    if isinstance(value, str):
        return _Period.from_string(value)
    return value


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


class OverviewCalendarRange(BaseModel):
    """Inclusive date window for the ``overview calendar`` query.

    :func:`aeat.application.overview.build_overview_calendar` expands the
    window to the covered filing years and filters legal obligation rows back to
    this inclusive range.
    """

    model_config = _STRICT_FROZEN

    from_date: date
    to_date: date

    @model_validator(mode="after")
    def _enforce_window_order(self) -> OverviewCalendarRange:
        if self.from_date > self.to_date:
            raise ValueError(f"OverviewCalendarRange.from_date ({self.from_date}) is after to_date ({self.to_date})")
        return self

    def covered_years(self) -> tuple[int, ...]:
        earliest = self.from_date.year - 1
        return tuple(range(earliest, self.to_date.year + 1))

    def covers(self, candidate: date) -> bool:
        return self.from_date <= candidate <= self.to_date


class OverviewCalendarFilingEvidence(BaseModel):
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
    filing_year: int | None = Field(default=None, ge=2000, le=2099)
    period: _Period | None = None
    local_filing_state: OverviewLocalFilingState = OverviewLocalFilingState.NOT_READY_TO_FILE
    local_filing_record_id: str | None = Field(default=None, min_length=1, max_length=128)
    local_calculation_revision_id: str | None = Field(default=None, min_length=1, max_length=128)
    local_filed_at: datetime | None = None
    aeat_submission_state: OverviewAeatSubmissionState = OverviewAeatSubmissionState.NOT_OBSERVED
    aeat_submitted_at: datetime | None = None
    aeat_reference_id: str | None = Field(default=None, min_length=1, max_length=128)
    aeat_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    aeat_evidence_kind: str | None = Field(default=None, min_length=1, max_length=64)
    aeat_evidence_conflict_reference_ids: tuple[str, ...] = Field(default_factory=tuple)
    verified_justificante_csv: str | None = Field(default=None, min_length=1, max_length=64)
    justificante_required: bool = True
    justificante_verified: bool = False
    evidence_source: str | None = Field(default=None, min_length=1, max_length=64)

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: _Period | None) -> str | None:
        return str(value) if value is not None else None

    @field_validator("period", mode="before")
    @classmethod
    def _hydrate_period(cls, value: object) -> object:
        return _period_from_serialized(value)

    @model_validator(mode="after")
    def _enforce_justificante_state_consistency(self) -> OverviewCalendarFilingEvidence:
        state_is_verified = self.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
        if self.justificante_verified != state_is_verified:
            raise ValueError(
                "OverviewCalendarFilingEvidence.justificante_verified must be true exactly when "
                "aeat_submission_state is justificante_verified",
            )
        if self.justificante_verified and self.verified_justificante_csv is None:
            raise ValueError(
                "OverviewCalendarFilingEvidence.verified_justificante_csv is required when "
                "justificante_verified is true",
            )
        if not self.justificante_verified and self.verified_justificante_csv is not None:
            raise ValueError(
                "OverviewCalendarFilingEvidence.verified_justificante_csv cannot be set unless "
                "justificante_verified is true",
            )
        return self


class OverviewCalendarEntry(BaseModel):
    """One legal ``(modelo, period)`` row in the calendar view.

    The deadline fields mirror :class:`~aeat.domain.deadlines.ModeloDeadline`.
    The optional :class:`OverviewCalendarFilingEvidence` row attaches local and
    AEAT evidence without changing the legal deadline status from the deadline
    engine.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: _Period
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
    filing_year: int | None = Field(default=None, ge=2000, le=2099)
    censo_enrolment_state: OverviewCensoEnrolmentState = OverviewCensoEnrolmentState.NOT_CHECKED
    filing_evidence: OverviewCalendarFilingEvidence = Field(default_factory=lambda: OverviewCalendarFilingEvidence())

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: _Period) -> str:
        return str(value)

    @field_validator("period", mode="before")
    @classmethod
    def _hydrate_period(cls, value: object) -> object:
        return _period_from_serialized(value)

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


class OverviewCalendarEventType(StrEnum):
    """Observed event categories shown alongside legal filing windows."""

    FILING = "filing"
    MESSAGE = "message"


class OverviewCalendarEvent(BaseModel):
    """One observed local event attached to an overview calendar range.

    Filing events may carry :class:`OverviewAeatSubmissionState` when a
    persisted snapshot already observed it. Messages and unverified filings
    remain event-only observations and do not imply
    :class:`OverviewCalendarFilingEvidence` or receipt verification.
    """

    model_config = _STRICT_FROZEN

    event_type: OverviewCalendarEventType
    event_date: date
    source: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=256)
    reference_id: str = Field(min_length=1, max_length=128)
    snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    modelo: str | None = Field(default=None, min_length=1, max_length=8)
    filing_year: int | None = Field(default=None, ge=2000, le=2099)
    period: _Period | None = None
    status: str | None = Field(default=None, max_length=64)
    source_url: str | None = Field(default=None, max_length=512)
    authenticated_identity: str | None = Field(default=None, max_length=32, exclude=True)
    aeat_submission_state: OverviewAeatSubmissionState | None = None
    aeat_submitted_at: datetime | None = None
    justificante_verified: bool | None = None
    verified_justificante_csv: str | None = Field(default=None, min_length=1, max_length=64)

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: _Period | None) -> str | None:
        return str(value) if value is not None else None

    @field_validator("period", mode="before")
    @classmethod
    def _hydrate_period(cls, value: object) -> object:
        return _period_from_serialized(value)

    @model_validator(mode="after")
    def _enforce_justificante_state_consistency(self) -> OverviewCalendarEvent:
        if self.aeat_submission_state is None and self.justificante_verified is None:
            return self
        if self.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED:
            if self.justificante_verified is not True:
                raise ValueError(
                    "OverviewCalendarEvent.justificante_verified must be true when "
                    "aeat_submission_state is justificante_verified",
                )
            if self.verified_justificante_csv is None:
                raise ValueError(
                    "OverviewCalendarEvent.verified_justificante_csv is required when justificante_verified is true",
                )
            return self
        if self.justificante_verified is True:
            raise ValueError(
                "OverviewCalendarEvent.justificante_verified cannot be true unless "
                "aeat_submission_state is justificante_verified",
            )
        if self.verified_justificante_csv is not None:
            raise ValueError(
                "OverviewCalendarEvent.verified_justificante_csv cannot be set unless "
                "aeat_submission_state is justificante_verified",
            )
        return self


class CalendarWarning(BaseModel):
    """One under-specified-profile warning attached to a calendar query."""

    model_config = _STRICT_FROZEN

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=128)
    fix_command: str = Field(min_length=1, max_length=256)
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
    period: _Period
    verdict: ApplicabilityVerdict
    reason: str = Field(min_length=1)

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: _Period) -> str:
        return str(value)

    @field_validator("period", mode="before")
    @classmethod
    def _hydrate_period(cls, value: object) -> object:
        return _period_from_serialized(value)


class OverviewCalendar(BaseModel):
    """Result of an ``aeat app overview calendar`` query.

    ``entries`` contains legal filing windows, ``events`` contains additive
    local observations, and ``suppressed_entries`` preserves filtered
    applicability rows only when the caller explicitly requests them.
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


class OverviewStatusReport(BaseModel):
    """Current active-profile readiness counters for ``overview status``.

    Produced from :class:`~aeat.application.state_projection.OperatorStateProjection`
    by :func:`aeat.application.overview.overview_status_report_from_projection`.
    """

    model_config = _STRICT_FROZEN

    active_profile: str | None = None
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
