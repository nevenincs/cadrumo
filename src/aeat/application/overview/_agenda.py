"""Overview agenda: upcoming-deadline ranking with a top-of-payload next_due.

:func:`build_overview_agenda` is the application service backing
``aeat app overview agenda``. It accepts a :class:`TaxpayerProfile`
and composes :func:`build_overview_calendar` over a window anchored
on the operator's ``as_of`` date, then partitions the resulting entries
into ``overdue`` / ``due_today`` / ``due_soon`` cohorts and surfaces the
earliest future obligation as ``next_due`` so the CLI can render a
single "what is the next thing I have to do" answer without re-walking
the calendar.

Local-only: never contacts AEAT. Pure aggregator over the deadline
engine, the festivos table, and the operator's profile values.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field

from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time import now
from ...domain.deadlines import DeadlineEngine, TaxpayerProfile
from . import (
    CalendarCompleteness,
    CalendarWarning,
    OverviewCalendarEntry,
    OverviewCalendarRange,
    OverviewPeriodState,
    build_overview_calendar,
)
from ._errors import OverviewAgendaError

_DEFAULT_HORIZON_DAYS = 14
"""Default forward window for `due_soon` partitioning."""

_OVERDUE_LOOKBACK_DAYS = 90
"""How far back the overdue cohort is computed against."""


class OverviewAgenda(BaseModel):
    """Outcome of ``build_overview_agenda``.

    Attributes:
        as_of: Date the agenda is rendered against.
        horizon_days: Forward window the `due_soon` cohort honours.
        next_due: Single earliest future obligation (closest
            ``adjusted_closes_on >= as_of``); ``None`` when no future
            obligation falls inside the lookahead window.
        due_today: Entries whose ``adjusted_closes_on`` equals ``as_of``.
        due_soon: Entries whose ``adjusted_closes_on`` falls in
            ``(as_of, as_of + horizon_days]``.
        overdue: Entries whose ``adjusted_closes_on`` precedes ``as_of``
            and whose user_state is ``LATE`` (filed obligations are
            excluded — the engine's ``FILED`` flag suppresses them
            via the state mapping).
        generated_at: UTC timestamp of when the aggregator ran.
        warnings: Calendar warnings inherited from the underlying
            calendar build (under-specified profile keys).
        completeness: Calendar completeness inherited from the
            underlying calendar build.
        taxpayer_model_declared: Whether the profile carries a usable
            three-axis taxpayer model. When ``False`` every cohort is
            empty and the operator must declare their taxpayer type
            first.
        incomplete_reason: "declare your taxpayer type first" guidance,
            present only when ``taxpayer_model_declared`` is ``False``.
    """

    model_config = _STRICT_FROZEN

    as_of: date
    horizon_days: int = Field(gt=0, le=365)
    next_due: OverviewCalendarEntry | None = None
    due_today: tuple[OverviewCalendarEntry, ...] = ()
    due_soon: tuple[OverviewCalendarEntry, ...] = ()
    overdue: tuple[OverviewCalendarEntry, ...] = ()
    generated_at: datetime
    warnings: tuple[CalendarWarning, ...] = ()
    completeness: CalendarCompleteness = Field(default_factory=CalendarCompleteness)
    taxpayer_model_declared: bool = True
    incomplete_reason: str | None = None


def build_overview_agenda(
    profile: TaxpayerProfile,
    *,
    as_of: date,
    horizon_days: int = _DEFAULT_HORIZON_DAYS,
    engine: DeadlineEngine | None = None,
    raw_values: Mapping[str, object] | None = None,
) -> OverviewAgenda:
    """Rank upcoming and past-due obligations around ``as_of``.

    Args:
        profile: The :class:`TaxpayerProfile` whose obligations are ranked.
        as_of: Anchor date for the lookback / lookahead window.
        horizon_days: Number of days after ``as_of`` to include in the
            lookahead window.
        engine: Optional :class:`DeadlineEngine` override; defaults to the
            registry-backed engine when ``None``.
        raw_values: Optional mapping of registry binding raw values forwarded
            to the deadline engine for context-sensitive deadlines.

    Composes :func:`build_overview_calendar` over a window that spans
    ``as_of - 90 days`` (so overdue obligations from the prior quarter
    surface) through ``as_of + horizon_days`` (so the lookahead matches
    the operator's requested ``--horizon``).

    The returned ``next_due`` is the single entry with the smallest
    ``adjusted_closes_on >= as_of``; if multiple obligations close on
    the same date, the deterministic calendar ordering
    ``(closes_on, modelo, period)`` resolves the tie.

    Returns an :class:`OverviewAgenda`.
    """
    if horizon_days <= 0:
        raise OverviewAgendaError(f"horizon_days must be positive; got {horizon_days}")

    window = OverviewCalendarRange(
        from_date=as_of - timedelta(days=_OVERDUE_LOOKBACK_DAYS),
        to_date=as_of + timedelta(days=horizon_days),
    )
    calendar = build_overview_calendar(
        profile,
        window,
        today=as_of,
        engine=engine,
        raw_values=raw_values,
    )

    horizon_end = as_of + timedelta(days=horizon_days)
    due_today: list[OverviewCalendarEntry] = []
    due_soon: list[OverviewCalendarEntry] = []
    overdue: list[OverviewCalendarEntry] = []
    next_due: OverviewCalendarEntry | None = None
    for entry in calendar.entries:
        deadline = entry.adjusted_closes_on
        if deadline == as_of:
            due_today.append(entry)
        elif as_of < deadline <= horizon_end:
            due_soon.append(entry)
        elif deadline < as_of and entry.user_state is OverviewPeriodState.LATE:
            overdue.append(entry)

    future_or_today = [entry for entry in calendar.entries if entry.adjusted_closes_on >= as_of]
    if future_or_today:
        next_due = min(
            future_or_today,
            key=lambda entry: (entry.adjusted_closes_on, entry.modelo, entry.period.year, entry.period.registry_token),
        )

    return OverviewAgenda(
        as_of=as_of,
        horizon_days=horizon_days,
        next_due=next_due,
        due_today=tuple(due_today),
        due_soon=tuple(due_soon),
        overdue=tuple(overdue),
        generated_at=now(),
        warnings=calendar.warnings,
        completeness=calendar.completeness,
        taxpayer_model_declared=calendar.taxpayer_model_declared,
        incomplete_reason=calendar.incomplete_reason,
    )


__all__ = [
    "OverviewAgenda",
    "build_overview_agenda",
]
