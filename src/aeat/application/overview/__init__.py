"""Typed overview-status surface for ``aeat app overview``.

The CLI exposes::

    aeat app overview status                                # bare readiness
    aeat app overview status --period {period} --verbose
    aeat app overview calendar --from DATE --to DATE

The calendar view uses a closed 4-state user-facing taxonomy that maps
from the existing :class:`aeat.domain.deadlines.ObligationStatus`
six-state enum. The typed query record
(:class:`OverviewCalendarRange`), the per-period entry record
(:class:`OverviewCalendarEntry`), the result wrapper
(:class:`OverviewCalendar`), the user-facing state enum
(:class:`OverviewPeriodState`), and the
:func:`build_overview_calendar` aggregator that composes the existing
:class:`aeat.domain.deadlines.DeadlineEngine` over the year window.

The aggregator is pure: no I/O, no mutation. The CLI wires it to the
operator's active profile and the parsed ``--from`` / ``--to`` dates.

When the caller supplies ``raw_values`` (the operator's user_cli
profile values mapping), the aggregator additionally detects which
deadline-engine-consumed keys are unset and surfaces a typed
``CalendarWarning`` per missing key plus a ``CalendarCompleteness``
breakdown listing computable / under-default modelos. The
profile-completeness surface ensures the engine never silently
computes obligations from its defaults without flagging that the
operator never declared a gating field.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...domain.deadlines import (
    DeadlineEngine,
    HolidayJurisdiction,
    ModeloDeadline,
    ObligationStatus,
    Recovery,
    Schedule,
    TaxpayerProfile,
    shift_deadline,
)
from ...domain.deadlines._festivos import DeadlineValidationError
from ._errors import (
    OverviewAgendaError,
    OverviewBacklogError,
    OverviewCalendarError,
    OverviewError,
    OverviewExplainError,
)

if TYPE_CHECKING:
    from ..state_projection import OperatorStateProjection
    from ..workflow import WorkflowState

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
"""Shared :class:`pydantic.ConfigDict` for overview records."""


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


_USER_STATE_FOR_OBLIGATION_STATUS: MappingProxyType[ObligationStatus, OverviewPeriodState] = MappingProxyType(
    {
        ObligationStatus.UPCOMING: OverviewPeriodState.DUE,
        ObligationStatus.DUE_SOON: OverviewPeriodState.DUE,
        ObligationStatus.DUE_TODAY: OverviewPeriodState.DUE,
        ObligationStatus.OVERDUE: OverviewPeriodState.LATE,
        ObligationStatus.FILED: OverviewPeriodState.FILED,
        ObligationStatus.NOT_APPLICABLE: OverviewPeriodState.UNKNOWN,
    }
)
"""Translates the 6-state engine status into the CLI's 4-state taxonomy."""


def user_state_for(obligation_status: ObligationStatus) -> OverviewPeriodState:
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
        """Return the calendar years the range spans, oldest first."""
        return tuple(range(self.from_date.year, self.to_date.year + 1))

    def covers(self, candidate: date) -> bool:
        """Return whether ``candidate`` lies inside the inclusive range."""
        return self.from_date <= candidate <= self.to_date


class OverviewCalendarEntry(BaseModel):
    """One ``(modelo, period)`` row in the calendar view.

    Mirrors :class:`aeat.domain.deadlines.ModeloDeadline` fields the
    CLI table needs, plus the precomputed user state so renderers
    do not re-derive the mapping at every call site.

    Attributes:
        modelo: Modelo identifier.
        period: Canonical period string (e.g. ``"2026Q1"``).
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
        recovery: Resolved :class:`Recovery` payload when ``status`` is
            ``OVERDUE``; ``None`` otherwise. Carried through verbatim
            from the underlying :class:`ModeloDeadline`.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    opens_on: date
    closes_on: date
    adjusted_closes_on: date
    shift_reason: str = Field(min_length=1, max_length=64)
    holiday_refs: tuple[str, ...] = Field(default_factory=tuple)
    jurisdictions: tuple[HolidayJurisdiction, ...] = Field(default_factory=tuple)
    payment_cutoff_on: date | None = None
    status: ObligationStatus
    user_state: OverviewPeriodState
    recovery: Recovery | None = None

    @model_validator(mode="after")
    def _enforce_window_order(self) -> OverviewCalendarEntry:
        """Reject entries whose window or payment cutoff is inverted."""
        if self.opens_on > self.closes_on:
            raise ValueError(f"OverviewCalendarEntry.opens_on ({self.opens_on}) is after closes_on ({self.closes_on})")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise ValueError(
                f"OverviewCalendarEntry.payment_cutoff_on ({self.payment_cutoff_on}) "
                f"is after closes_on ({self.closes_on})"
            )
        if self.adjusted_closes_on < self.closes_on:
            raise ValueError(
                f"OverviewCalendarEntry.adjusted_closes_on ({self.adjusted_closes_on}) "
                f"precedes closes_on ({self.closes_on}); the shift rule may only move "
                f"a deadline forward."
            )
        return self

    @model_validator(mode="after")
    def _enforce_user_state_consistency(self) -> OverviewCalendarEntry:
        """The precomputed user_state must match the engine status mapping."""
        expected = _USER_STATE_FOR_OBLIGATION_STATUS[self.status]
        if self.user_state is not expected:
            raise ValueError(
                f"OverviewCalendarEntry.user_state ({self.user_state}) "
                f"disagrees with engine status mapping ({expected})"
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
        message: Translation key the renderer feeds through ``tr``.
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


class OverviewCalendar(BaseModel):
    """Result of an ``aeat app overview calendar`` query.

    Attributes:
        range: The :class:`OverviewCalendarRange` the query was scoped
            to.
        entries: Tuple of :class:`OverviewCalendarEntry` rows ordered
            by ``(closes_on, modelo, period)`` — same key the engine
            uses, so the CLI table is deterministic.
        generated_at: UTC timestamp of when the aggregator ran. The
            only non-deterministic field.
        warnings: Tuple of :class:`CalendarWarning` rows for every
            under-specified profile key the engine relied on a default
            for. Empty when the operator declared every gating key.
        completeness: Per-key / per-modelo breakdown of explicit vs
            defaulted resolution. Always present; carries empty
            tuples when no ``raw_values`` was supplied at build time.
    """

    model_config = _STRICT_FROZEN

    range: OverviewCalendarRange
    entries: tuple[OverviewCalendarEntry, ...]
    generated_at: datetime
    warnings: tuple[CalendarWarning, ...] = Field(default=())
    completeness: CalendarCompleteness = Field(default_factory=CalendarCompleteness)


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


def _entry_intersects_range(
    obligation: ModeloDeadline,
    calendar_range: OverviewCalendarRange,
) -> bool:
    """Return whether ``obligation``'s [opens_on, closes_on] intersects the range."""
    return obligation.closes_on >= calendar_range.from_date and obligation.opens_on <= calendar_range.to_date


_GATING_FIELDS: MappingProxyType[str, tuple[tuple[str, ...], str, str]] = MappingProxyType(
    {
        "iva.regime": (
            ("303", "390"),
            "cli.overview.warning.iva_regime_unset",
            "aeat config profile edit",
        ),
        "does_intracomunitario": (
            ("349",),
            "cli.overview.warning.intracomunitario_unset",
            "aeat config profile edit",
        ),
        "pays_professionals_with_retencion": (
            ("111",),
            "cli.overview.warning.retencion_profesionales_unset",
            "aeat config profile edit",
        ),
        "pays_rent_with_retencion": (
            ("115",),
            "cli.overview.warning.retencion_arrendamientos_unset",
            "aeat config profile edit",
        ),
        "uses_objective_estimation_irpf": (
            ("131",),
            "cli.overview.warning.estimacion_objetiva_unset",
            "aeat config profile edit",
        ),
    }
)
"""Profile keys the deadline engine reads when classifying applicability,
mapped to ``(affected_modelos, message_key, fix_command)``. The list is the
audit-named subset; future engine extensions can add rows here without
changing the warning-rendering plumbing."""


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
            )
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


def build_overview_calendar(
    profile: TaxpayerProfile,
    calendar_range: OverviewCalendarRange,
    *,
    today: date,
    engine: DeadlineEngine | None = None,
    raw_values: Mapping[str, object] | None = None,
) -> OverviewCalendar:
    """Build a typed calendar view for ``profile`` over ``calendar_range``.

    Composes the existing :class:`aeat.domain.deadlines.DeadlineEngine`
    over each year the range spans, filters obligations to those whose
    filing window intersects the range, attaches the user-state
    mapping, and returns the typed result.

    Args:
        profile: The operator's :class:`TaxpayerProfile`.
        calendar_range: Inclusive date window to enumerate.
        today: Reference date for engine status classification.
        engine: Optional :class:`DeadlineEngine` instance the caller
            wants to share across queries. When ``None``, a default
            engine is constructed.

    Returns:
        A :class:`OverviewCalendar` with one entry per
        ``(modelo, period)`` whose filing window intersects the range.

    Raises:
        ValueError: When the engine cannot compute a year inside the
            range. Re-raised verbatim from
            :class:`aeat.domain.deadlines.ScheduleComputationError`.
    """
    deadline_engine = engine if engine is not None else DeadlineEngine()
    schedules: list[Schedule] = []
    for year in calendar_range.covered_years():
        schedules.append(deadline_engine.compute(profile, year, today=today))

    entries: list[OverviewCalendarEntry] = []
    for schedule in schedules:
        for obligation in schedule.obligations:
            if not _entry_intersects_range(obligation, calendar_range):
                continue
            try:
                shift = shift_deadline(
                    obligation.closes_on,
                    modelo=obligation.modelo,
                    ccaa_code=None,
                )
                adjusted = shift.adjusted_close_date
                reason = shift.shift_reason
                holiday_refs = shift.holiday_refs
                jurisdictions = shift.jurisdictions
            except DeadlineValidationError:
                # Holiday calendar not registered for this year; degrade
                # gracefully — surface the original close date and an
                # explicit reason so renderers can show that no shift
                # was applied.
                adjusted = obligation.closes_on
                reason = "calendar_unavailable"
                holiday_refs = ()
                jurisdictions = ()
            entries.append(
                OverviewCalendarEntry(
                    modelo=obligation.modelo,
                    period=obligation.period,
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
                )
            )

    entries.sort(key=lambda entry: (entry.closes_on, entry.modelo, entry.period))
    entries_tuple = tuple(entries)
    completeness, warnings = _build_completeness_and_warnings(raw_values, entries_tuple)
    return OverviewCalendar(
        range=calendar_range,
        entries=entries_tuple,
        generated_at=datetime.now(UTC),
        warnings=warnings,
        completeness=completeness,
    )


def overview_status_report_from_projection(projection: OperatorStateProjection) -> OverviewStatusReport:
    """Project the canonical state projection into the ``overview status`` emit shape.

    The :class:`OverviewStatusReport` is a CLI emit shape derived from
    the one :class:`OperatorStateProjection`; it is not a second
    state-assembly path. Both the legacy ``ModeloDraft`` count and the
    ``WorkUnitCatalogue`` count are carried distinctly.
    """

    return OverviewStatusReport(
        active_profile=projection.active_profile.profile_id,
        active_profile_name=projection.active_profile.label,
        transactions=projection.workspace.transactions,
        invoices=projection.workspace.invoices,
        drafts=projection.workspace.drafts,
        work_units=projection.workspace.work_units,
        discarded_work_units=projection.workspace.discarded_work_units,
        calculation_revisions=projection.workspace.calculation_revisions,
        unreadable_rows=projection.workspace.unreadable_rows,
    )


def build_overview_status_report(
    *,
    state: WorkflowState | None = None,
) -> OverviewStatusReport:
    """Build the typed readiness report used by root and overview status.

    Consumes the canonical :func:`build_operator_state_projection`; the
    bespoke per-surface store assembly this function once carried is
    deleted. ``overview status`` therefore reports the same counters as
    every other operator surface — including the ``modelo work`` work
    units the old assembly never read.
    """

    from ..state_projection import build_operator_state_projection

    projection = build_operator_state_projection(state=state)
    return overview_status_report_from_projection(projection)


def render_overview_status_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    """Render ``OverviewStatusReport`` as stable tab-separated text rows."""

    lines = [
        f"profile\t{report.active_profile_name or report.active_profile or ''}",
        f"profile_id\t{report.active_profile or ''}",
        f"transactions\t{report.transactions}",
        f"invoices\t{report.invoices}",
        f"drafts\t{report.drafts}",
        f"work_units\t{report.work_units}",
        f"discarded_work_units\t{report.discarded_work_units}",
        f"calculation_revisions\t{report.calculation_revisions}",
    ]
    if report.unreadable_rows > 0:
        lines.append(f"integrity-warning\tunreadable_rows={report.unreadable_rows}")
    return tuple(lines)


__all__ = [
    "CalendarCompleteness",
    "CalendarWarning",
    "OverviewAgendaError",
    "OverviewBacklogError",
    "OverviewCalendar",
    "OverviewCalendarEntry",
    "OverviewCalendarError",
    "OverviewCalendarRange",
    "OverviewError",
    "OverviewExplainError",
    "OverviewPeriodState",
    "OverviewStatusReport",
    "build_overview_calendar",
    "build_overview_status_report",
    "overview_status_report_from_projection",
    "render_overview_status_lines",
    "user_state_for",
]
