"""Real-behavior tests for ``build_overview_agenda``."""

from __future__ import annotations

from datetime import date

import pytest

from ....core import Period
from ..agenda import OverviewAgenda, build_overview_agenda
from ..errors import OverviewAgendaError
from .calendar_test_support import profile as _profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_agenda_horizon_must_be_positive() -> None:
    """A non-positive horizon is refused at the service boundary."""

    with pytest.raises(OverviewAgendaError) as exc_info:
        build_overview_agenda(_profile(), as_of=date(2026, 1, 15), horizon_days=0)
    # The refusal carries a typed translated_message key + context, not a raw
    # args[0] string; assert the locale-independent identity.
    assert exc_info.value.translated_message == "application.overview.errors.horizon_days_not_positive"
    assert exc_info.value.context is not None
    assert exc_info.value.context["horizon_days"] == 0


def test_agenda_returns_typed_envelope_with_required_fields() -> None:
    """The aggregator produces an OverviewAgenda envelope carrying the
    as_of date, horizon, generated_at, and the four cohort tuples."""

    agenda = build_overview_agenda(_profile(), as_of=date(2026, 1, 15))

    assert isinstance(agenda, OverviewAgenda)
    assert agenda.as_of == date(2026, 1, 15)
    assert agenda.horizon_days == 14
    assert isinstance(agenda.due_today, tuple)
    assert isinstance(agenda.due_soon, tuple)
    assert isinstance(agenda.overdue, tuple)


def test_agenda_next_due_is_earliest_future_or_today_deadline() -> None:
    """When the calendar contains any entry with adjusted_closes_on >=
    as_of, next_due points at the earliest one. The deterministic tie-
    break uses (closes_on, modelo, period)."""

    agenda = build_overview_agenda(_profile(), as_of=date(2026, 1, 1), horizon_days=120)

    if agenda.next_due is not None:
        # All entries with adjusted_closes_on >= as_of must close on or
        # after the chosen next_due date.
        future_entries = list(agenda.due_today) + list(agenda.due_soon)
        for entry in future_entries:
            assert entry.adjusted_closes_on >= agenda.next_due.adjusted_closes_on


def test_agenda_partitions_entries_by_deadline_position() -> None:
    """due_today entries close on as_of; due_soon entries close in
    (as_of, as_of+horizon]; overdue entries close before as_of and
    carry LATE state."""

    as_of = date(2026, 4, 15)
    agenda = build_overview_agenda(_profile(), as_of=as_of, horizon_days=30)

    for entry in agenda.due_today:
        assert entry.adjusted_closes_on == as_of
    for entry in agenda.due_soon:
        assert as_of < entry.adjusted_closes_on <= date(2026, 5, 15)
    for entry in agenda.overdue:
        assert entry.adjusted_closes_on < as_of
        # Overdue cohort excludes already-filed obligations; the
        # state taxonomy maps OVERDUE -> LATE in user_state.
        assert entry.user_state.value == "late"


def test_agenda_partitions_are_disjoint() -> None:
    """The same (modelo, period) cannot appear in more than one cohort."""

    agenda = build_overview_agenda(_profile(), as_of=date(2026, 4, 15), horizon_days=30)

    seen: set[tuple[str, Period]] = set()
    for cohort in (agenda.due_today, agenda.due_soon, agenda.overdue):
        for entry in cohort:
            key = (entry.modelo, entry.period)
            assert key not in seen, f"duplicate {key} across cohorts"
            seen.add(key)
