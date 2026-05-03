"""Typed overview-status surface for ``aeat app overview``.

The CLI exposes::

    aeat app overview status                                # bare readiness
    aeat app overview status --calendar --from DATE --to DATE
    aeat app overview status --period PERIOD --verbose

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
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...domain.deadlines import (
    AutonomoProfile,
    DeadlineEngine,
    FilingObligation,
    ObligationStatus,
    Schedule,
)

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
    """Inclusive date window for the ``overview status --calendar`` query.

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

    Mirrors :class:`aeat.domain.deadlines.FilingObligation` fields the
    CLI table needs, plus the precomputed user state so renderers
    do not re-derive the mapping at every call site.

    Attributes:
        modelo: Modelo identifier (e.g. ``"130"``, ``"303"``).
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
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    status: ObligationStatus
    user_state: OverviewPeriodState

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


class OverviewCalendar(BaseModel):
    """Result of an ``aeat app overview status --calendar`` query.

    Attributes:
        range: The :class:`OverviewCalendarRange` the query was scoped
            to.
        entries: Tuple of :class:`OverviewCalendarEntry` rows ordered
            by ``(closes_on, modelo, period)`` — same key the engine
            uses, so the CLI table is deterministic.
        generated_at: UTC timestamp of when the aggregator ran. The
            only non-deterministic field.
    """

    model_config = _STRICT_FROZEN

    range: OverviewCalendarRange
    entries: tuple[OverviewCalendarEntry, ...]
    generated_at: datetime


def _entry_intersects_range(
    obligation: FilingObligation,
    calendar_range: OverviewCalendarRange,
) -> bool:
    """Return whether ``obligation``'s [opens_on, closes_on] intersects the range."""
    return obligation.closes_on >= calendar_range.from_date and obligation.opens_on <= calendar_range.to_date


def build_overview_calendar(
    profile: AutonomoProfile,
    calendar_range: OverviewCalendarRange,
    *,
    today: date,
    engine: DeadlineEngine | None = None,
) -> OverviewCalendar:
    """Build a typed calendar view for ``profile`` over ``calendar_range``.

    Composes the existing :class:`aeat.domain.deadlines.DeadlineEngine`
    over each year the range spans, filters obligations to those whose
    filing window intersects the range, attaches the user-state
    mapping, and returns the typed result.

    Args:
        profile: The operator's :class:`AutonomoProfile`.
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
            entries.append(
                OverviewCalendarEntry(
                    modelo=obligation.modelo,
                    period=obligation.period,
                    opens_on=obligation.opens_on,
                    closes_on=obligation.closes_on,
                    payment_cutoff_on=obligation.payment_cutoff_on,
                    status=obligation.status,
                    user_state=user_state_for(obligation.status),
                )
            )

    entries.sort(key=lambda entry: (entry.closes_on, entry.modelo, entry.period))
    return OverviewCalendar(
        range=calendar_range,
        entries=tuple(entries),
        generated_at=datetime.now(UTC),
    )


__all__ = [
    "OverviewCalendar",
    "OverviewCalendarEntry",
    "OverviewCalendarRange",
    "OverviewPeriodState",
    "build_overview_calendar",
    "user_state_for",
]
