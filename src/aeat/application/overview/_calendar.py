"""Calendar aggregation and evidence merge for the overview application facade.

Use of :class:`Schedule`, :class:`TaxpayerProfile` for compliance. Derives
per-deadline filing evidence from filed :class:`ModeloRecord` rows so the
calendar reflects which obligations already carry a justificante.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_serializer, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period as _Period
from ...core.external_constants import IVA_REGIME_MODELOS
from ...core.i18n import tr as _tr
from ...core.logging import get_logger as _get_logger
from ...core.time import now
from ...domain.calculations.registry.applicability import ApplicabilityVerdict, derive_modelo_applicability
from ...domain.calculations.registry.applicability import PayerFact as _PayerFact
from ...domain.calculations.registry.applicability import (
    iter_modelo_applicability_rules as _iter_modelo_applicability_rules,
)
from ...domain.calculations.registry.applicability import taxpayer_model_is_declared as _taxpayer_model_is_declared
from ...domain.deadlines import DeadlineEngine as _DeadlineEngine
from ...domain.deadlines import HolidayJurisdiction as _HolidayJurisdiction
from ...domain.deadlines import ModeloDeadline as _ModeloDeadline
from ...domain.deadlines import ObligationStatus as _ObligationStatus
from ...domain.deadlines import Recovery as _Recovery
from ...domain.deadlines import Schedule as _Schedule
from ...domain.deadlines import ScheduleProducer as _ScheduleProducer
from ...domain.deadlines import TaxpayerProfile as _TaxpayerProfile
from ...domain.deadlines import shift_deadline as _shift_deadline
from ...domain.deadlines._errors import NoDeadlineWindowsError as _NoDeadlineWindowsError
from ...domain.deadlines._festivos import DeadlineValidationError as _DeadlineValidationError
from ...domain.deadlines.taxpayer_model import IrpfEstimationRegime as _IrpfEstimationRegime

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.sede import FiledDeclaracionObservation
    from ...domain.justificante import Justificante
    from ...domain.modelos import ModeloRecord
    from ..live._expedientes import PersistedExpedientesSnapshot
    from ..live._notifications import PersistedNotificationsSnapshot

_log = _get_logger(__name__)

class OverviewPeriodState(StrEnum):
    """Closed 4-state user-facing period state for the calendar view.

    The CLI renders one row per ``(modelo, period)`` pair; the row's
    state column is one of these values. The mapping from
    :class:`aeat.domain.deadlines.ObligationStatus` is in
    :data:`_USER_STATE_FOR_OBLIGATION_STATUS`.

    Attributes:
        DUE: Filing window is open and not past its close date.
            Maps from ``UPCOMING`` / ``DUE_SOON`` / ``DUE_TODAY``.
        LATE: Filing window has closed. Maps from ``OVERDUE``.
        FILED: Operator has already filed this period. Maps from the
            downstream ``FILED`` marker.
        UNKNOWN: The obligation does not apply, or local state is not
            available. Maps from ``NOT_APPLICABLE``.
    """

    DUE = "due"
    LATE = "late"
    FILED = "filed"
    UNKNOWN = "unknown"


class OverviewLocalFilingState(StrEnum):
    """Local application-side filing readiness for a calendar obligation.

    This is deliberately separate from real-world AEAT submission. In
    this application, a local filing record means a verified calculation
    revision was marked as the current answer ready for external filing;
    it does not mean the return was sent to AEAT.
    """

    NOT_READY_TO_FILE = "not_ready_to_file"
    READY_TO_FILE = "ready_to_file"
    EXTERNAL_BASELINE_IMPORTED = "external_baseline_imported"


class OverviewAeatSubmissionState(StrEnum):
    """Observed AEAT-side submission evidence for a calendar obligation."""

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
"""Translates the 6-state engine status into the CLI's 4-state taxonomy."""

_AEAT_SUBMISSION_RANK: MappingProxyType[OverviewAeatSubmissionState, int] = MappingProxyType(
    {
        OverviewAeatSubmissionState.NOT_OBSERVED: 0,
        OverviewAeatSubmissionState.SUBMITTED_OBSERVED: 1,
        OverviewAeatSubmissionState.ACCEPTED: 2,
        OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: 3,
    },
)
"""Merge priority for multiple AEAT evidence sources about the same period."""

_JUSTIFICANTE_BACKED_EVIDENCE_KINDS = frozenset({"aeat_justificante_pdf", "aeat_live_capture"})
"""External evidence kinds that require persisted justificante metadata before verification."""


def user_state_for(obligation_status: _ObligationStatus) -> OverviewPeriodState:
    """Return the :class:`OverviewPeriodState` for an engine status."""
    return _USER_STATE_FOR_OBLIGATION_STATUS[obligation_status]


class OverviewCalendarRange(BaseModel):
    """Inclusive date window for the ``overview calendar`` query.

    Attributes:
        from_date: Inclusive earliest date the operator wants to see
            obligations for. Validated against ``to_date``.
        to_date: Inclusive latest date.
    """

    model_config = _STRICT_FROZEN

    from_date: date
    to_date: date

    @model_validator(mode="after")
    def _enforce_window_order(self) -> OverviewCalendarRange:
        """Reject ranges where ``from_date`` is after ``to_date``."""
        if self.from_date > self.to_date:
            raise ValueError(f"OverviewCalendarRange.from_date ({self.from_date}) is after to_date ({self.to_date})")
        return self

    def covered_years(self) -> tuple[int, ...]:
        """Return the fiscal years whose deadline windows may intersect this range.

        AEAT annual declarations (e.g. Modelo 200 IS, Modelo 100 Renta) use
        ``filing_year = N`` for the tax period that ends on 31 December of year
        N, but the filing deadline falls in calendar year N+1 (e.g. IS for 2024
        opens 1 July 2025). A calendar query scoped to a date range that starts
        in January of N+1 must therefore also query ``deadline_windows(N)`` to
        pick up those prior-year declarations whose windows open in the query
        range. Including ``from_date.year - 1`` ensures a single-calendar-year
        range (e.g. 2025-01-01 to 2025-12-31) fetches both the 2024 fiscal-year
        windows that open in 2025 and the native 2025 fiscal-year windows.
        """
        earliest = self.from_date.year - 1
        return tuple(range(earliest, self.to_date.year + 1))

    def covers(self, candidate: date) -> bool:
        """Return whether ``candidate`` lies inside the inclusive range."""
        return self.from_date <= candidate <= self.to_date


class OverviewCalendarFilingEvidence(BaseModel):
    """Filing evidence attached to one legal calendar obligation.

    The local and AEAT axes are independent. A local filing record can
    be ready to file while AEAT submission remains unobserved. An
    imported AEAT justificante can verify AEAT submission even when the
    application did not compute the filing locally.
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
    justificante_required: bool = True
    justificante_verified: bool = False
    evidence_source: str | None = Field(default=None, min_length=1, max_length=64)

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: _Period | None) -> str | None:
        return str(value) if value is not None else None

    @model_validator(mode="after")
    def _enforce_justificante_state_consistency(self) -> OverviewCalendarFilingEvidence:
        """Keep the AEAT submission state and justificante boolean in lockstep."""
        state_is_verified = self.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
        if self.justificante_verified != state_is_verified:
            raise ValueError(
                "OverviewCalendarFilingEvidence.justificante_verified must be true exactly when "
                "aeat_submission_state is justificante_verified",
            )
        return self


class OverviewCalendarEntry(BaseModel):
    """One ``(modelo, period)`` row in the calendar view.

    Mirrors :class:`aeat.domain.deadlines.ModeloDeadline` fields the
    CLI table needs, plus the precomputed user state so renderers
    do not re-derive the mapping at every call site.

    Attributes:
        modelo: Modelo identifier.
        period: Filing period as a typed :class:`~aeat.core.Period` value.
        opens_on: First day the filing window accepts submissions.
        closes_on: Last day the filing window accepts submissions.
        payment_cutoff_on: Direct-debit payment cutoff. ``None`` when
            no payment leg applies.
        status: Underlying engine
            :class:`aeat.domain.deadlines.ObligationStatus`. Carried so
            CLI renderers that want the 6-state granularity (e.g.
            ``due-soon`` vs ``upcoming``) do not have to walk back to
            the engine.
        user_state: Precomputed :class:`OverviewPeriodState` derived
            via :func:`user_state_for` for the CLI's 4-column table.
        recovery: Resolved :class:`_Recovery` payload when ``status`` is
            ``OVERDUE``; ``None`` otherwise. Carried through verbatim
            from the underlying :class:`ModeloDeadline`.
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
    filing_evidence: OverviewCalendarFilingEvidence = Field(default_factory=lambda: OverviewCalendarFilingEvidence())

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: _Period) -> str:
        return str(value)

    @model_validator(mode="after")
    def _enforce_window_order(self) -> OverviewCalendarEntry:
        """Reject entries whose window or payment cutoff is inverted."""
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
        """The precomputed user_state must match the engine status mapping."""
        expected = _USER_STATE_FOR_OBLIGATION_STATUS[self.status]
        if self.user_state is not expected:
            raise ValueError(
                f"OverviewCalendarEntry.user_state ({self.user_state}) "
                f"disagrees with engine status mapping ({expected})",
            )
        return self


class OverviewCalendarEventType(StrEnum):
    """Observed local event types shown alongside legal filing windows."""

    FILING = "filing"
    MESSAGE = "message"


class OverviewCalendarEvent(BaseModel):
    """One observed local event attached to an overview calendar range.

    Calendar entries remain the legal obligation rows. Events are
    already-observed facts from local persisted live-read snapshots:
    AEAT filed declarations and AEAT notifications/communications.
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
    aeat_submission_state: OverviewAeatSubmissionState | None = None
    justificante_verified: bool | None = None

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: _Period | None) -> str | None:
        return str(value) if value is not None else None

    @model_validator(mode="after")
    def _enforce_justificante_state_consistency(self) -> OverviewCalendarEvent:
        """Reject calendar events that report contradictory AEAT filing evidence."""
        if self.aeat_submission_state is None and self.justificante_verified is None:
            return self
        if self.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED:
            if self.justificante_verified is not True:
                raise ValueError(
                    "OverviewCalendarEvent.justificante_verified must be true when "
                    "aeat_submission_state is justificante_verified",
                )
            return self
        if self.justificante_verified is True:
            raise ValueError(
                "OverviewCalendarEvent.justificante_verified cannot be true unless "
                "aeat_submission_state is justificante_verified",
            )
        return self


class CalendarWarning(BaseModel):
    """One under-specified-profile warning attached to a calendar query.

    Surfaces when a deadline-engine-consumed profile key is unset in
    the operator's user_cli state. The engine has already returned a
    schedule under default values for that key, so the calendar IS
    computable -- but the operator must verify the default matches
    their actual regime / enrolment. The warning carries the
    "calendar computed under defaults the operator never confirmed"
    semantic so renderers can prompt the operator to declare the
    gating field.

    Attributes:
        code: Stable warning identifier (e.g.
            ``profile.iva_regime_unset``).
        message: Translation key the renderer feeds through ``_tr``.
        fix_command: Concrete shell command the operator can run to
            address the warning (e.g.
            ``aeat config profile edit``).
        affected_modelos: Tuple of modelo identifiers whose
            applicability rule reads the missing key.
    """

    model_config = _STRICT_FROZEN

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=128)
    fix_command: str = Field(min_length=1, max_length=256)
    affected_modelos: tuple[str, ...] = Field(default=())


class CalendarCompleteness(BaseModel):
    """Breakdown of which modelos are computed under explicit values vs defaults.

    Attributes:
        explicitly_set_keys: Profile keys the operator declared and
            whose values the engine read.
        defaulted_keys: Profile keys the operator left unset; the
            engine fell back to its built-in defaults for these.
        computable_modelos: Modelos that appear in the returned
            schedule under the resolved (possibly defaulted) values.
        defaulted_modelos: Subset of ``computable_modelos`` whose
            applicability rule depends on at least one defaulted
            key. The operator may want to re-run the calendar after
            confirming the regime.
    """

    model_config = _STRICT_FROZEN

    explicitly_set_keys: tuple[str, ...] = Field(default=())
    defaulted_keys: tuple[str, ...] = Field(default=())
    computable_modelos: tuple[str, ...] = Field(default=())
    defaulted_modelos: tuple[str, ...] = Field(default=())


class SuppressedCalendarEntry(BaseModel):
    """One filtered (non-applicable) obligation when ``--show-suppressed`` is set.

    Carries the minimal envelope needed for the operator to understand
    why a modelo was dropped from the active calendar: the modelo
    identifier, the period, the applicability verdict, and the
    operator-facing reason prose.

    Attributes:
        modelo: Modelo identifier.
        period: Suppressed filing period as a typed :class:`~aeat.core.Period` value.
        verdict: The :class:`ApplicabilityVerdict` that caused the entry
            to be suppressed (``NOT_APPLICABLE``, ``ATTRIBUTION_PASS_THROUGH``,
            or ``INCOMPLETE``).
        reason: Operator-facing prose explaining the verdict, sourced
            from the rule's ``not_applicable_reason`` or the
            ``INCOMPLETE`` rationale.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: _Period
    verdict: ApplicabilityVerdict
    reason: str = Field(min_length=1)

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: _Period) -> str:
        return str(value)


class OverviewCalendar(BaseModel):
    """Result of an ``aeat app overview calendar`` query.

    Attributes:
        range: The :class:`OverviewCalendarRange` the query was scoped
            to.
        entries: Tuple of :class:`OverviewCalendarEntry` rows ordered
            by ``(closes_on, modelo, period)`` — same key the engine
            uses, so the CLI table is deterministic. Only modelos with a
            positively ``APPLICABLE`` applicability verdict appear:
            obligations the taxpayer model excludes (e.g. Modelo 130 for
            a pure landlord) and modelos the seed rule table cannot yet
            decide (``INCOMPLETE``) are filtered out, keeping the
            calendar consistent with ``explain``. An undeclared
            taxpayer model yields an empty tuple plus
            ``taxpayer_model_declared = False``.
        generated_at: UTC timestamp of when the aggregator ran. The
            only non-deterministic field.
        warnings: Tuple of :class:`CalendarWarning` rows for every
            under-specified profile key the engine relied on a default
            for. Empty when the operator declared every gating key.
        completeness: Per-key / per-modelo breakdown of explicit vs
            defaulted resolution. Always present; carries empty
            tuples when no ``raw_values`` was supplied at build time.
        taxpayer_model_declared: Whether the profile carries a usable
            three-axis taxpayer model. When ``False`` the calendar is
            empty and the operator must declare their taxpayer type
            first — the engine never reports a confident wrong
            obligation.
        incomplete_reason: Operator-facing "declare your taxpayer type
            first" guidance, present only when
            ``taxpayer_model_declared`` is ``False``.
        suppressed_entries: Tuple of :class:`SuppressedCalendarEntry`
            rows for obligations that were filtered out due to a
            non-``APPLICABLE`` applicability verdict. Populated only
            when ``show_suppressed=True`` was passed to
            :func:`build_overview_calendar`; empty otherwise. Ordered
            by ``(modelo, period)`` for deterministic output.
        events: Tuple of :class:`OverviewCalendarEvent` rows projected
            from already-persisted local live-read snapshots. These are
            observed AEAT facts, not derived legal obligations.
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

    Derived from the canonical :class:`OperatorStateProjection`; this
    report is the CLI emit shape, not a second state-assembly path.
    """

    model_config = _STRICT_FROZEN

    active_profile: str | None = None
    """Immutable bucket UUID of the active profile, or ``None``."""
    active_profile_name: str | None = None
    """Operator-chosen display name of the active profile, or ``None``."""
    transactions: int = Field(ge=0)
    invoices: int = Field(ge=0)
    drafts: int = Field(ge=0)
    work_units: int = Field(default=0, ge=0)
    """Count of *active* (``BORRADOR``) ``WorkUnitCatalogue`` entries.

    Carried distinctly from ``drafts`` (the legacy ``ModeloDraft``
    store) so an operator who used the ``modelo work`` flow does not
    see a silently-zero counter. Discarded units are excluded here and
    counted in ``discarded_work_units`` so the operator is never told a
    misleading total.
    """
    discarded_work_units: int = Field(default=0, ge=0)
    """Count of ``DESCARTADO`` ``WorkUnitCatalogue`` entries.

    Surfaced alongside ``work_units`` so ``overview status`` can state
    the active / discarded split instead of a single inflated count.
    """
    calculation_revisions: int = Field(default=0, ge=0)
    """Count of ``CalculationRevisionCatalogue`` entries written by ``modelo work calculate``."""
    unreadable_rows: int = Field(ge=0)
    filing_obligation_advisories: tuple[str, ...] = Field(default=())
    """Locale-key advisory strings for filing obligations derived from the profile.

    Each entry is a ``tr()``-resolvable locale key whose rendered text
    explains a mandatory filing obligation the profile data implies.
    Currently populated for the Art. 96.3 LIRPF multiple-pagadores rule.
    Empty when no obligation evidence is present in the profile.
    """


def _entry_intersects_range(
    obligation: _ModeloDeadline,
    calendar_range: OverviewCalendarRange,
) -> bool:
    """Return whether ``obligation``'s [opens_on, closes_on] intersects the range."""
    return obligation.closes_on >= calendar_range.from_date and obligation.opens_on <= calendar_range.to_date


def _calendar_event_sort_key(event: OverviewCalendarEvent) -> tuple[date, str, str, str]:
    """Return the deterministic sort key for observed calendar events."""
    return (
        event.event_date,
        event.event_type.value,
        event.modelo or "",
        event.reference_id,
    )


def _dedupe_calendar_events(events: list[OverviewCalendarEvent]) -> tuple[OverviewCalendarEvent, ...]:
    """Deduplicate repeated observations across multiple local snapshots."""
    by_key: dict[tuple[object, ...], OverviewCalendarEvent] = {}
    for event in events:
        key = (
            event.event_type,
            event.event_date,
            event.source,
            event.reference_id,
            event.modelo,
            event.filing_year,
            event.period,
        )
        by_key[key] = event
    return tuple(sorted(by_key.values(), key=_calendar_event_sort_key))


def calendar_events_from_expedientes_snapshots(
    snapshots: tuple[PersistedExpedientesSnapshot, ...],
    calendar_range: OverviewCalendarRange,
) -> tuple[OverviewCalendarEvent, ...]:
    """Project persisted AEAT declaration-register snapshots into :class:`OverviewCalendarEvent` tuples."""
    events: list[OverviewCalendarEvent] = []
    for snapshot in sorted(snapshots, key=lambda item: item.captured_at):
        for declaration in snapshot.declarations:
            event_date = declaration.presented_at.date()
            if not calendar_range.covers(event_date):
                continue
            _period = declaration.period
            summary = f"Modelo {declaration.modelo} {declaration.ejercicio} {_period.registry_token} filed at AEAT"
            aeat_submission_state = (
                OverviewAeatSubmissionState.SUBMITTED_OBSERVED
                if _is_active_aeat_filing_status(declaration.estado)
                else None
            )
            events.append(
                OverviewCalendarEvent(
                    event_type=OverviewCalendarEventType.FILING,
                    event_date=event_date,
                    source="aeat_sede_expedientes",
                    summary=summary,
                    reference_id=declaration.expediente_id,
                    snapshot_id=snapshot.snapshot_id,
                    modelo=declaration.modelo,
                    filing_year=declaration.ejercicio,
                    period=_period,
                    status=declaration.estado,
                    source_url=snapshot.source_url,
                    aeat_submission_state=aeat_submission_state,
                    justificante_verified=False if aeat_submission_state is not None else None,
                ),
            )
    return _dedupe_calendar_events(events)


def calendar_events_from_notification_snapshots(
    snapshots: tuple[PersistedNotificationsSnapshot, ...],
    calendar_range: OverviewCalendarRange,
) -> tuple[OverviewCalendarEvent, ...]:
    """Project persisted AEAT notifications and communications into :class:`OverviewCalendarEvent` tuples."""
    events: list[OverviewCalendarEvent] = []
    for snapshot in sorted(snapshots, key=lambda item: item.captured_at):
        for row in snapshot.rows:
            event_date = row.fecha_notificacion or row.fecha_emision
            if not calendar_range.covers(event_date):
                continue
            read_state = "read" if row.leida is True else "unread" if row.leida is False else None
            status = read_state or row.tipo
            summary = row.concepto.strip() or row.tipo
            events.append(
                OverviewCalendarEvent(
                    event_type=OverviewCalendarEventType.MESSAGE,
                    event_date=event_date,
                    source="aeat_sede_notifications",
                    summary=summary,
                    reference_id=row.certificado_id,
                    snapshot_id=snapshot.snapshot_id,
                    status=status,
                    source_url=str(row.source_url),
                ),
            )
    return _dedupe_calendar_events(events)


def build_overview_calendar_events(
    *,
    calendar_range: OverviewCalendarRange,
    expedientes_snapshots: tuple[PersistedExpedientesSnapshot, ...] = (),
    notification_snapshots: tuple[PersistedNotificationsSnapshot, ...] = (),
) -> tuple[OverviewCalendarEvent, ...]:
    """Build :class:`OverviewCalendarEvent` tuples from persisted local live-read snapshots."""
    events = [
        *calendar_events_from_expedientes_snapshots(expedientes_snapshots, calendar_range),
        *calendar_events_from_notification_snapshots(notification_snapshots, calendar_range),
    ]
    return _dedupe_calendar_events(events)


def calendar_filing_evidence_from_sources(
    *,
    filing_records: tuple[ModeloRecord, ...] = (),
    observed_events: tuple[OverviewCalendarEvent, ...] = (),
    filed_declaration_observations: tuple[FiledDeclaracionObservation, ...] = (),
    calculation_observations: tuple[object, ...] = (),
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[OverviewCalendarFilingEvidence, ...]:
    """Build :class:`OverviewCalendarFilingEvidence` tuples from local records and AEAT observations.

    The function is pure and intentionally accepts already-loaded
    records. CLI/storage code owns I/O; this projection only reconciles
    the existing local Modelo filing catalogue, calendar-visible AEAT
    register events, persisted calculation observations from
    justificante capture, and already-loaded justificante metadata. The
    ``filing_records`` are filed :class:`ModeloRecord` rows whose
    external justificante references are only promoted to
    ``justificante_verified`` when matching persisted metadata exists
    for the same CSV/model/year/period/taxpayer.
    """
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence] = {}  # (modelo, year, registry_token)
    event_specific: list[OverviewCalendarFilingEvidence] = []
    justificantes_by_csv = _justificantes_by_csv(justificantes)
    for record in filing_records:
        evidence = _filing_evidence_from_modelo_record(
            record,
            justificantes_by_csv=justificantes_by_csv,
            expected_tax_id=expected_tax_id,
        )
        if evidence is not None:
            _merge_filing_evidence(by_key, evidence)
    for event in observed_events:
        evidence = _filing_evidence_from_observed_event(event)
        if evidence is not None:
            _merge_filing_evidence(by_key, evidence)
    for observation in filed_declaration_observations:
        evidence = _filing_evidence_from_filed_declaration_observation(
            observation,
            expected_tax_id=expected_tax_id,
        )
        if evidence is not None:
            event_specific.append(evidence)
            _merge_filing_evidence(by_key, evidence)
    for payload in calculation_observations:
        evidence = _filing_evidence_from_calculation_observation(payload, expected_tax_id=expected_tax_id)
        if evidence is not None:
            _merge_filing_evidence(by_key, evidence)
    unique: dict[
        tuple[str | None, int | None, str | None, str | None], OverviewCalendarFilingEvidence
    ] = {}
    for evidence in (*by_key.values(), *event_specific):
        key_reference = (
            evidence.aeat_reference_id if evidence.evidence_source == "filed_declaration_observation" else None
        )
        _period_token = evidence.period.registry_token if evidence.period is not None else None
        unique[(evidence.modelo, evidence.filing_year, _period_token, key_reference)] = evidence
    return tuple(sorted(unique.values(), key=_calendar_filing_evidence_sort_key))


def _justificantes_by_csv(justificantes: tuple[Justificante, ...]) -> dict[str, Justificante]:
    """Index loaded justificante metadata by CSV/reference identifier."""
    by_csv: dict[str, Justificante] = {}
    for justificante in justificantes:
        csv = justificante.csv.strip()
        if csv:
            by_csv[csv] = justificante
    return by_csv


def _filing_evidence_from_modelo_record(
    record: ModeloRecord,
    *,
    justificantes_by_csv: Mapping[str, Justificante],
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project one local Modelo filing record into calendar evidence."""
    if record.status.value.lower() != "vigente":
        return None
    modelo = str(record.modelo)
    filing_year = int(record.filing_year)
    period = record.period
    external_evidence = record.external_evidence
    local_state = (
        OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED
        if external_evidence is not None
        else OverviewLocalFilingState.READY_TO_FILE
    )
    aeat_state = OverviewAeatSubmissionState.NOT_OBSERVED
    aeat_evidence_kind = None
    aeat_reference_id = None
    justificante_verified = False
    if bool(getattr(record, "aeat_accepted", False)):
        aeat_state = OverviewAeatSubmissionState.ACCEPTED
    if external_evidence is not None:
        kind = getattr(external_evidence, "kind", None)
        aeat_evidence_kind = str(getattr(kind, "value", kind))
        aeat_reference_id = str(external_evidence.reference_id)
        if aeat_evidence_kind in _JUSTIFICANTE_BACKED_EVIDENCE_KINDS and _modelo_record_has_verified_justificante(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            reference_id=aeat_reference_id,
            justificantes_by_csv=justificantes_by_csv,
            expected_tax_id=expected_tax_id,
        ):
            aeat_state = OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
            justificante_verified = True
        elif aeat_state is OverviewAeatSubmissionState.NOT_OBSERVED:
            aeat_state = OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    return OverviewCalendarFilingEvidence(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        local_filing_state=local_state,
        local_filing_record_id=str(record.filing_record_id),
        local_calculation_revision_id=str(record.calculation_revision_id),
        local_filed_at=record.filed_at,
        aeat_submission_state=aeat_state,
        aeat_reference_id=aeat_reference_id,
        aeat_evidence_kind=aeat_evidence_kind,
        justificante_verified=justificante_verified,
        evidence_source="modelo_filing_record",
    )


def _modelo_record_has_verified_justificante(
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    reference_id: str,
    justificantes_by_csv: Mapping[str, Justificante],
    expected_tax_id: str | None,
) -> bool:
    """Return whether a Modelo record's external reference resolves to matching justificante metadata."""
    expected = (expected_tax_id or "").strip()
    if not expected:
        return False
    justificante = justificantes_by_csv.get(reference_id.strip())
    if justificante is None:
        return False
    if justificante.tax_id.strip() != expected:
        return False
    if justificante.modelo.strip() != modelo:
        return False
    if str(justificante.ejercicio or "").strip() != str(filing_year):
        return False
    return justificante.period == period


def _filing_evidence_from_observed_event(
    event: OverviewCalendarEvent,
) -> OverviewCalendarFilingEvidence | None:
    """Project an AEAT calendar event into per-obligation evidence."""
    if event.event_type is not OverviewCalendarEventType.FILING:
        return None
    if event.modelo is None or event.filing_year is None or event.period is None:
        return None
    if event.status is not None and not _is_active_aeat_filing_status(event.status):
        return None
    state = event.aeat_submission_state
    if state is None:
        return None
    return OverviewCalendarFilingEvidence(
        modelo=event.modelo,
        filing_year=event.filing_year,
        period=event.period,
        aeat_submission_state=state,
        aeat_submitted_at=datetime.combine(event.event_date, datetime.min.time(), tzinfo=UTC),
        aeat_reference_id=event.reference_id,
        aeat_snapshot_id=event.snapshot_id,
        justificante_verified=bool(event.justificante_verified),
        evidence_source=event.source,
    )


def _filing_evidence_from_filed_declaration_observation(
    observation: FiledDeclaracionObservation,
    *,
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project a captured AEAT filed-declaration observation into calendar evidence."""
    expected = (expected_tax_id or "").strip()
    if expected and observation.authenticated_identity.strip() != expected:
        return None
    if not _is_active_aeat_filing_status(observation.status):
        return None
    justificante = next(
        (
            artefact
            for artefact in observation.artefacts
            if artefact.kind == "justificante_pdf" and artefact.storage_ref and artefact.byte_count > 0
        ),
        None,
    )
    verified = justificante is not None
    return OverviewCalendarFilingEvidence(
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
        aeat_submission_state=(
            OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
            if verified
            else OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        ),
        aeat_submitted_at=observation.presented_at,
        aeat_reference_id=observation.expediente_id,
        aeat_evidence_kind="aeat_justificante_pdf" if verified else "filed_declaration_observation",
        justificante_verified=verified,
        evidence_source="filed_declaration_observation",
    )


def _is_active_aeat_filing_status(status: str | None) -> bool:
    """Return whether an AEAT register row represents the current accepted filing."""
    return (status or "").strip().upper() == "ALTA"


def _filing_evidence_from_calculation_observation(
    payload: object,
    *,
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project a persisted calculation observation into AEAT-submitted evidence."""
    source_kind = str(getattr(payload, "source_kind", ""))
    if source_kind != "aeat_sede_justificante":
        return None
    source_metadata = getattr(payload, "source_metadata", None)
    source_metadata = source_metadata if isinstance(source_metadata, Mapping) else {}
    if not source_metadata:
        return None
    status = str(source_metadata.get("aeat_register_status", "")).strip()
    if not _is_active_aeat_filing_status(status):
        return None
    expected = (expected_tax_id or "").strip().upper()
    authenticated_identity = str(source_metadata.get("authenticated_identity", "")).strip().upper()
    if expected and (not authenticated_identity or authenticated_identity != expected):
        return None
    observation = getattr(payload, "observation", None)
    if observation is None:
        return None
    _obs_year = int(observation.filing_year)
    registry_token = observation.period
    if not isinstance(registry_token, str):
        return None
    _obs_period = _period_from_registry_token(_obs_year, registry_token)
    return OverviewCalendarFilingEvidence(
        modelo=str(observation.modelo),
        filing_year=_obs_year,
        period=_obs_period,
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        aeat_submitted_at=getattr(payload, "captured_at", None),
        aeat_reference_id=str(source_metadata.get("aeat_expediente_id") or "") or None,
        aeat_evidence_kind=source_kind,
        justificante_verified=False,
        evidence_source=source_kind,
    )


def _period_from_registry_token(filing_year: int, registry_token: str) -> _Period:
    return _Period.from_year_and_code(filing_year, registry_token)


def _merge_filing_evidence(
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence],
    candidate: OverviewCalendarFilingEvidence,
) -> None:
    """Merge one evidence row into the canonical (modelo, year, registry_token) key."""
    if candidate.modelo is None or candidate.filing_year is None or candidate.period is None:
        return
    key = (candidate.modelo, candidate.filing_year, candidate.period.registry_token)
    existing = by_key.get(key)
    merged = candidate if existing is None else _stronger_filing_evidence(existing, candidate)
    by_key[key] = merged


def _stronger_filing_evidence(
    existing: OverviewCalendarFilingEvidence,
    candidate: OverviewCalendarFilingEvidence,
) -> OverviewCalendarFilingEvidence:
    """Return a merged evidence row preserving the strongest signal on each axis."""
    local = existing
    if (
        existing.local_filing_state is OverviewLocalFilingState.NOT_READY_TO_FILE
        and candidate.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE
    ):
        local = local.model_copy(
            update={
                "local_filing_state": candidate.local_filing_state,
                "local_filing_record_id": candidate.local_filing_record_id,
                "local_calculation_revision_id": candidate.local_calculation_revision_id,
                "local_filed_at": candidate.local_filed_at,
            },
        )
    if _AEAT_SUBMISSION_RANK[candidate.aeat_submission_state] >= _AEAT_SUBMISSION_RANK[local.aeat_submission_state]:
        local = local.model_copy(
            update={
                "aeat_submission_state": candidate.aeat_submission_state,
                "aeat_submitted_at": candidate.aeat_submitted_at or local.aeat_submitted_at,
                "aeat_reference_id": candidate.aeat_reference_id or local.aeat_reference_id,
                "aeat_snapshot_id": candidate.aeat_snapshot_id or local.aeat_snapshot_id,
                "aeat_evidence_kind": candidate.aeat_evidence_kind or local.aeat_evidence_kind,
                "justificante_verified": candidate.justificante_verified or local.justificante_verified,
                "evidence_source": candidate.evidence_source or local.evidence_source,
            },
        )
    return local


def _calendar_filing_evidence_sort_key(
    evidence: OverviewCalendarFilingEvidence,
) -> tuple[str, int, str]:
    _p = evidence.period
    return (evidence.modelo or "", evidence.filing_year or 0, _p.registry_token if _p is not None else "")


def _calendar_entry_filing_evidence(
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> OverviewCalendarFilingEvidence:
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence] = {}
    for item in evidence:
        _merge_filing_evidence(by_key, item)
    match = by_key.get((modelo, filing_year, period.registry_token))
    if match is not None:
        return match.model_copy(update={"modelo": modelo, "filing_year": filing_year, "period": period})
    return OverviewCalendarFilingEvidence(modelo=modelo, filing_year=filing_year, period=period)


def _calendar_events_with_filing_evidence(
    events: tuple[OverviewCalendarEvent, ...],
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> tuple[OverviewCalendarEvent, ...]:
    enriched: list[OverviewCalendarEvent] = []
    for event in events:
        if event.event_type is not OverviewCalendarEventType.FILING:
            enriched.append(event)
            continue
        if event.status is not None and not _is_active_aeat_filing_status(event.status):
            enriched.append(event)
            continue
        if event.modelo is None or event.filing_year is None or event.period is None:
            enriched.append(event)
            continue
        row = _calendar_event_filing_evidence(event=event, evidence=evidence)
        if row is None:
            enriched.append(event)
            continue
        current_state = event.aeat_submission_state or OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        if _AEAT_SUBMISSION_RANK[row.aeat_submission_state] <= _AEAT_SUBMISSION_RANK[current_state]:
            enriched.append(event)
            continue
        enriched.append(
            event.model_copy(
                update={
                    "aeat_submission_state": row.aeat_submission_state,
                    "justificante_verified": row.justificante_verified,
                },
            ),
        )
    return _dedupe_calendar_events(enriched)


def _calendar_event_filing_evidence(
    *,
    event: OverviewCalendarEvent,
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> OverviewCalendarFilingEvidence | None:
    if event.modelo is None or event.filing_year is None or event.period is None:
        return None
    if event.status is not None and not _is_active_aeat_filing_status(event.status):
        return None
    matching_refs = tuple(
        item
        for item in evidence
        if item.aeat_reference_id == event.reference_id
        and item.modelo == event.modelo
        and item.filing_year == event.filing_year
        and item.period is not None
        and item.period.registry_token == event.period.registry_token
    )
    if not matching_refs:
        return None
    row = matching_refs[0]
    for candidate in matching_refs[1:]:
        row = _stronger_filing_evidence(row, candidate)
    return row


_PAYER_FACT_PROFILE_KEY: dict[_PayerFact, tuple[str, str]] = {
    _PayerFact.PAYS_WITHHELD_INCOME: (
        "pays_professionals_with_retencion",
        "cli.overview.warning.retencion_profesionales_unset",
    ),
    _PayerFact.PAYS_RENT_WITH_RETENCION: (
        "pays_rent_with_retencion",
        "cli.overview.warning.retencion_arrendamientos_unset",
    ),
    _PayerFact.TRADES_INTRACOMMUNITY: (
        "does_intracomunitario",
        "cli.overview.warning.intracomunitario_unset",
    ),
    _PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD: (
        "third_party_transactions_above_347_threshold",
        "cli.overview.warning.terceros_threshold_unset",
    ),
}

_ESTIMATION_REGIME_PROFILE_KEY: dict[_IrpfEstimationRegime, tuple[str, str]] = {
    _IrpfEstimationRegime.OBJETIVA: (
        "uses_objective_estimation_irpf",
        "cli.overview.warning.estimacion_objetiva_unset",
    ),
}

_IVA_REGIME_MODELOS = IVA_REGIME_MODELOS


def _gating_fields() -> MappingProxyType[str, tuple[tuple[str, ...], str, str]]:
    """Derive the profile-key → (affected_modelos, message_key, fix_command) mapping.

    Iterates :data:`~aeat.domain.calculations.registry._applicability._MODELO_APPLICABILITY_RULES`
    and builds the completeness-warning table from the rule axes rather than
    maintaining a hardcoded dict. New rules whose gates use a known _PayerFact
    or estimation regime automatically surface their gating warning without a
    manual update here.

    Three rule axes produce gating-field entries:

    * ``required_payer_fact`` — maps to a profile boolean via
      :data:`_PAYER_FACT_PROFILE_KEY`.
    * ``required_estimation_regimes`` — when a rule gates on a single
      non-directa regime, maps to a profile key via
      :data:`_ESTIMATION_REGIME_PROFILE_KEY`.
    * IVA-subject modelos — static set :data:`_IVA_REGIME_MODELOS`
      mapped to the ``iva.regime`` profile key (IVA regime is not yet
      encoded in the rule schema).

    The ``fix_command`` is always ``"aeat config profile edit"`` — all
    gating fields are settable via the profile-edit surface.
    """
    _FIX = "aeat config profile edit"
    key_to_modelos: dict[str, set[str]] = {}
    key_to_meta: dict[str, tuple[str, str]] = {}

    for rule in _iter_modelo_applicability_rules():
        if rule.required_payer_fact is not None:
            payer_fact_meta = _PAYER_FACT_PROFILE_KEY.get(rule.required_payer_fact)
            if payer_fact_meta is not None:
                profile_key, locale_key = payer_fact_meta
                key_to_modelos.setdefault(profile_key, set()).add(rule.modelo)
                key_to_meta[profile_key] = (locale_key, _FIX)

        if len(rule.required_estimation_regimes) == 1:
            (regime,) = rule.required_estimation_regimes
            if regime in _ESTIMATION_REGIME_PROFILE_KEY:
                profile_key, locale_key = _ESTIMATION_REGIME_PROFILE_KEY[regime]
                key_to_modelos.setdefault(profile_key, set()).add(rule.modelo)
                key_to_meta[profile_key] = (locale_key, _FIX)

    key_to_modelos["iva.regime"] = set(_IVA_REGIME_MODELOS)
    key_to_meta["iva.regime"] = ("cli.overview.warning.iva_regime_unset", _FIX)

    return MappingProxyType(
        {
            profile_key: (
                tuple(sorted(key_to_modelos[profile_key])),
                key_to_meta[profile_key][0],
                key_to_meta[profile_key][1],
            )
            for profile_key in sorted(key_to_modelos)
        },
    )


_GATING_FIELDS: MappingProxyType[str, tuple[tuple[str, ...], str, str]] = _gating_fields()
"""Profile keys derived from :data:`_MODELO_APPLICABILITY_RULES` that the
deadline engine reads when classifying applicability, mapped to
``(affected_modelos, message_key, fix_command)``.

Built by :func:`_gating_fields` at import time from the canonical rule
table so new rules automatically surface their gating warnings without
a manual update to this mapping."""


def _build_completeness_and_warnings(
    raw_values: Mapping[str, object] | None,
    entries: tuple[OverviewCalendarEntry, ...],
) -> tuple[CalendarCompleteness, tuple[CalendarWarning, ...]]:
    """Inspect the raw profile values and compute warnings + completeness."""
    if raw_values is None:
        return CalendarCompleteness(), ()
    explicitly_set: list[str] = []
    defaulted: list[str] = []
    warnings: list[CalendarWarning] = []
    defaulted_modelos: set[str] = set()
    for key, (affected_modelos, message_key, fix_command) in _GATING_FIELDS.items():
        raw = raw_values.get(key)
        if raw is not None and str(raw).strip():
            explicitly_set.append(key)
            continue
        defaulted.append(key)
        warnings.append(
            CalendarWarning(
                code=key,
                message=message_key,
                fix_command=fix_command,
                affected_modelos=affected_modelos,
            ),
        )
        defaulted_modelos.update(affected_modelos)
    computable_modelos = tuple(sorted({entry.modelo for entry in entries}))
    completeness = CalendarCompleteness(
        explicitly_set_keys=tuple(explicitly_set),
        defaulted_keys=tuple(defaulted),
        computable_modelos=computable_modelos,
        defaulted_modelos=tuple(sorted(defaulted_modelos & set(computable_modelos))),
    )
    return completeness, tuple(warnings)


def _calendar_entry_from_obligation(
    obligation: _ModeloDeadline,
    *,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> OverviewCalendarEntry:
    try:
        shift = _shift_deadline(
            obligation.closes_on,
            modelo=obligation.modelo,
            ccaa_code=None,
        )
        adjusted = shift.adjusted_close_date
        reason = shift.shift_reason
        holiday_refs = shift.holiday_refs
        jurisdictions = shift.jurisdictions
    except _DeadlineValidationError as exc:
        _log.debug(
            "overview calendar ignored deadline shift validation error",
            extra={
                "modelo": obligation.modelo,
                "period": obligation.period,
                "error_type": type(exc).__name__,
            },
        )
        adjusted = obligation.closes_on
        reason = "calendar_unavailable"
        holiday_refs = ()
        jurisdictions = ()
    period = obligation.period
    return OverviewCalendarEntry(
        modelo=obligation.modelo,
        period=period,
        opens_on=obligation.opens_on,
        closes_on=obligation.closes_on,
        adjusted_closes_on=adjusted,
        shift_reason=reason,
        holiday_refs=holiday_refs,
        jurisdictions=jurisdictions,
        payment_cutoff_on=obligation.payment_cutoff_on,
        status=obligation.status,
        user_state=user_state_for(obligation.status),
        recovery=obligation.recovery,
        filing_year=period.year,
        filing_evidence=_calendar_entry_filing_evidence(
            modelo=obligation.modelo,
            filing_year=period.year,
            period=period,
            evidence=filing_evidence,
        ),
    )


def build_overview_calendar(
    profile: _TaxpayerProfile,
    calendar_range: OverviewCalendarRange,
    *,
    today: date,
    engine: _ScheduleProducer | None = None,
    raw_values: Mapping[str, object] | None = None,
    show_suppressed: bool = False,
    events: tuple[OverviewCalendarEvent, ...] = (),
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...] = (),
) -> OverviewCalendar:
    """Build a typed calendar view for ``profile`` over ``calendar_range``.

    Composes the existing :class:`aeat.domain.deadlines.DeadlineEngine`
    over each year the range spans, filters obligations to those whose
    filing window intersects the range, attaches the user-state
    mapping, and returns the typed result.

    Args:
        profile: The operator's :class:`_TaxpayerProfile`.
        calendar_range: Inclusive date window to enumerate.
        today: Reference date for engine status classification.
        engine: Optional :class:`_ScheduleProducer` the caller wants to
            share across queries — a concrete
            :class:`aeat.domain.deadlines.DeadlineEngine` or any object
            satisfying the schedule-producing protocol. When ``None``,
            a default :class:`_DeadlineEngine` is constructed.
        raw_values: Optional mapping of casilla id to raw value, forwarded
            to the engine for user-state annotation. When ``None``, the
            engine uses an empty mapping.
        show_suppressed: When ``True``, populate
            :attr:`OverviewCalendar.suppressed_entries` with the
            obligations filtered out by a non-``APPLICABLE``
            applicability verdict. Default is ``False`` — the standard
            calendar view excludes suppressed rows from the payload
            entirely.
        events: Optional observed calendar events, usually projected
            from persisted local live-read snapshots by the CLI.
        filing_evidence: Optional local/AEAT evidence rows keyed to
            calendar obligations. These rows are preloaded by callers
            that own storage access; the calendar builder only merges
            them onto legal deadline entries.

    A year inside the range with no registered deadline windows is
    treated as a "no data yet" state: that year contributes zero
    entries and the calendar still succeeds for every year that does
    have window data. This is the same graceful degradation
    ``overview explain`` applies to a modelo/year pair with no
    registered windows.

    Returns:
        A :class:`OverviewCalendar` with one entry per
        ``(modelo, period)`` whose filing window intersects the range.
    """
    if not _taxpayer_model_is_declared(profile):
        # An undeclared taxpayer model yields an explicit
        # incomplete answer — never a confident wrong obligation. The
        # engine does not fall back to the autónomo guess.
        return OverviewCalendar(
            range=calendar_range,
            entries=(),
            generated_at=now(),
            warnings=(),
            completeness=CalendarCompleteness(),
            taxpayer_model_declared=False,
            incomplete_reason=_tr("cli.overview.taxpayer_model_undeclared"),
            events=_calendar_events_with_filing_evidence(events, filing_evidence),
        )

    deadline_engine = engine if engine is not None else _DeadlineEngine()
    schedules: list[_Schedule] = []
    for year in calendar_range.covered_years():
        try:
            schedules.append(deadline_engine.compute(profile, year, today=today))
        except _NoDeadlineWindowsError as exc:
            # A year inside the range with no registered deadline
            # windows is a normal "no data yet" state, not an error
            # (registry-track gap R1). The year contributes zero
            # entries; the calendar still answers for every year that
            # does have window data. This catch is deliberately the
            # narrow ``_NoDeadlineWindowsError`` subtype: a genuine
            # registry-integrity fault (validation failure,
            # profile-condition evaluation failure) raises the bare
            # ``ScheduleComputationError`` and must propagate — masking
            # it here would silently hide a corrupt registry. This
            # mirrors the graceful degradation ``overview explain``
            # applies via the same narrow catch.
            _log.debug(
                "overview calendar ignored covered year with no registered deadline windows",
                extra={"year": year, "error_type": type(exc).__name__},
            )
            continue

    entries: list[OverviewCalendarEntry] = []
    suppressed: list[SuppressedCalendarEntry] = []
    for schedule in schedules:
        for obligation in schedule.obligations:
            if not _entry_intersects_range(obligation, calendar_range):
                continue
            # Each modelo's applicability is DERIVED from the taxpayer
            # model. Only a positively ``APPLICABLE`` verdict earns a
            # calendar row. An obligation the taxpayer model excludes
            # (``NOT_APPLICABLE`` — e.g. Modelo 130 for a pure landlord)
            # is dropped; so is a cuota self-assessment routed to the
            # attribution pass-through (``ATTRIBUTION_PASS_THROUGH`` — a
            # comunidad de bienes owes no IS / IRPF cuota of its own);
            # so is a modelo the seed table cannot yet decide
            # (``INCOMPLETE`` — no seed rule). Surfacing any of these as
            # a confident due row would diverge from ``explain`` and
            # re-create the confident-wrong-obligation defect. The seed
            # covers the core persona set; full per-modelo coverage is a
            # deferred expansion (see ``_SEED_COVERAGE_NOTICE``).
            applicability = derive_modelo_applicability(profile, obligation.modelo)
            if applicability.verdict is not ApplicabilityVerdict.APPLICABLE:
                if show_suppressed:
                    suppressed.append(
                        SuppressedCalendarEntry(
                            modelo=obligation.modelo,
                            period=obligation.period,
                            verdict=applicability.verdict,
                            reason=applicability.reason,
                        ),
                    )
                continue
            entries.append(_calendar_entry_from_obligation(obligation, filing_evidence=filing_evidence))

    entries.sort(key=lambda entry: (entry.closes_on, entry.modelo, entry.period.year, entry.period.registry_token))
    suppressed.sort(key=lambda s: (s.modelo, s.period.year, s.period.registry_token))
    entries_tuple = tuple(entries)
    completeness, warnings = _build_completeness_and_warnings(raw_values, entries_tuple)
    return OverviewCalendar(
        range=calendar_range,
        entries=entries_tuple,
        generated_at=now(),
        warnings=warnings,
        completeness=completeness,
        suppressed_entries=tuple(suppressed),
        events=_calendar_events_with_filing_evidence(events, filing_evidence),
    )
