"""Overview backlog: past-due / triage cohort listing.

:func:`build_overview_backlog` is the application service backing
``aeat app overview backlog``. It accepts a :class:`TaxpayerProfile`,
composes :func:`build_overview_calendar` over an operator-supplied date
window (defaulting to the last 365 days through today), and enumerates
every obligation whose ``adjusted_closes_on`` precedes today AND whose
``user_state`` indicates it has not yet been filed.

The verb is a read model only: it never mutates state and never
contacts AEAT. Lifecycle continuation is owned by
``aeat app modelo resume`` per the workflow-resumption-semantics ADR.
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

_DEFAULT_LOOKBACK_DAYS = 365
"""Default lookback window when neither --from nor --to is supplied."""


class OverviewBacklog(BaseModel):
    """Outcome of ``build_overview_backlog``.

    Attributes:
        range: Calendar window the backlog was scoped to.
        as_of: Reference date the past-due cohort is computed against.
        items: Past-due obligations whose user_state is ``LATE`` and
            whose ``adjusted_closes_on`` precedes ``as_of``. Sorted
            ascending by deadline (oldest first) so operators triage
            the most-overdue obligations first.
        late_count: Number of items in ``items`` (cached for renderers
            that show a header summary without re-walking the list).
        generated_at: UTC timestamp of when the aggregator ran.
        warnings: Calendar warnings inherited from the underlying
            calendar build (under-specified profile keys).
        completeness: Calendar completeness inherited from the
            underlying calendar build.
        taxpayer_model_declared: Whether the profile carries a usable
            three-axis taxpayer model. When ``False`` the backlog is
            empty and the operator must declare their taxpayer type
            first.
        incomplete_reason: "declare your taxpayer type first" guidance,
            present only when ``taxpayer_model_declared`` is ``False``.
    """

    model_config = _STRICT_FROZEN

    range: OverviewCalendarRange
    as_of: date
    items: tuple[OverviewCalendarEntry, ...] = ()
    late_count: int = Field(ge=0)
    generated_at: datetime
    warnings: tuple[CalendarWarning, ...] = ()
    completeness: CalendarCompleteness = Field(default_factory=CalendarCompleteness)
    taxpayer_model_declared: bool = True
    incomplete_reason: str | None = None


def build_overview_backlog(
    profile: TaxpayerProfile,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    as_of: date | None = None,
    engine: DeadlineEngine | None = None,
    raw_values: Mapping[str, object] | None = None,
) -> OverviewBacklog:
    """Enumerate the operator's past-due obligations.

    Args:
        profile: The :class:`TaxpayerProfile` whose filing obligations are evaluated.
        from_date: Start of the calendar window; defaults to 365 days before ``as_of``.
        to_date: End of the calendar window; defaults to ``as_of``.
        as_of: Reference date for past-due classification; defaults to today.
        engine: Optional deadline engine override.
        raw_values: Optional raw profile values passed through to the engine.

    The default window is the 365 days preceding ``as_of`` (today
    when omitted), which is wide enough to surface every backlog
    item that survived a full annual filing cycle without overflowing
    the underlying deadline-engine schedule.

    Past-due classification uses the 4-state ``OverviewPeriodState``
    taxonomy: an obligation is in the backlog iff its
    ``adjusted_closes_on`` precedes ``as_of`` AND its ``user_state``
    is ``LATE``. Filed obligations are excluded by the state mapping;
    the engine surfaces them as ``FILED`` rather than ``OVERDUE``.

    Returns an :class:`OverviewBacklog` with the backlog items and the
    calendar range used for the computation.
    """
    resolved_as_of = as_of or date.today()
    resolved_from = from_date or (resolved_as_of - timedelta(days=_DEFAULT_LOOKBACK_DAYS))
    resolved_to = to_date or resolved_as_of
    window = OverviewCalendarRange(from_date=resolved_from, to_date=resolved_to)
    calendar = build_overview_calendar(
        profile,
        window,
        today=resolved_as_of,
        engine=engine,
        raw_values=raw_values,
    )

    items: list[OverviewCalendarEntry] = []
    for entry in calendar.entries:
        if entry.adjusted_closes_on < resolved_as_of and entry.user_state is OverviewPeriodState.LATE:
            items.append(entry)
    items.sort(
        key=lambda entry: (entry.adjusted_closes_on, entry.modelo, entry.period.year, entry.period.registry_token)
    )

    return OverviewBacklog(
        range=window,
        as_of=resolved_as_of,
        items=tuple(items),
        late_count=len(items),
        generated_at=now(),
        warnings=calendar.warnings,
        completeness=calendar.completeness,
        taxpayer_model_declared=calendar.taxpayer_model_declared,
        incomplete_reason=calendar.incomplete_reason,
    )


__all__ = [
    "OverviewBacklog",
    "build_overview_backlog",
]
