"""Closed calendar, agenda, and backlog overview projections."""

from __future__ import annotations

from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, NonNegativeInt

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .agenda import OverviewAgenda
from .backlog import OverviewBacklog
from .calendar_models import CalendarCompleteness, OverviewCalendar, OverviewCalendarRange
from .coverage import ObligationCoverageReport
from .read_calendar_item_projection import (
    OverviewCalendarEntrySnapshot,
    OverviewCalendarEventSnapshot,
    OverviewCalendarWarningSnapshot,
    OverviewSuppressedEntrySnapshot,
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
