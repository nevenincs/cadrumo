"""Pure-function deadline computation engine.

Takes an :class:`AutonomoProfile` and a year and produces a deterministic,
typed :class:`Schedule`. The engine performs **no I/O** after construction,
never mutates inputs, and never reaches for global state — the same
``(profile, year, today)`` always yields an equal schedule (modulo
:attr:`aeat.domain.deadlines.Schedule.generated_at`).

Pairs with :mod:`aeat.domain.deadlines._applies` for modelo applicability,
:mod:`aeat.domain.deadlines._calendar` for canonical filing windows, and
:mod:`aeat.domain.deadlines._models` for the value types it returns.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from ...core.logging import get_logger
from ._applies import applies_to, explain
from ._calendar import (
    CALENDAR,
    KNOWN_AUTONOMO_MODELOS,
    CanonicalWindow,
)
from ._errors import ScheduleComputationError
from ._models import (
    AutonomoProfile,
    FilingObligation,
    ObligationStatus,
    Schedule,
)

_logger = get_logger(__name__)

_DEFAULT_DUE_SOON_DAYS = 14


def _classify(closes_on: date, today: date, due_soon_days: int) -> ObligationStatus:
    """Map a window close date to an :class:`ObligationStatus`.

    Args:
        closes_on: The day the AEAT filing window closes.
        today: The reference date the engine evaluates against.
        due_soon_days: Window (in days) before ``closes_on`` for which
            the obligation is flagged ``DUE_SOON``.

    Returns:
        The :class:`ObligationStatus` for the window.
    """
    if today > closes_on:
        return ObligationStatus.OVERDUE
    if today == closes_on:
        return ObligationStatus.DUE_TODAY
    delta = (closes_on - today).days
    if 1 <= delta <= due_soon_days:
        return ObligationStatus.DUE_SOON
    return ObligationStatus.UPCOMING


def _windows_for_year(year: int) -> tuple[CanonicalWindow, ...]:
    """Return the canonical windows whose ``year`` field equals ``year``."""
    return tuple(window for window in CALENDAR if window.year == year)


class DeadlineEngine:
    """Pure-function engine that computes typed filing schedules.

    Stateless after construction. Modelo applicability is closed over the
    in-code :data:`aeat.domain.deadlines._calendar.KNOWN_AUTONOMO_MODELOS`
    set rather than a Protocol-injected catalogue: every modelo the engine
    reasons about lives in that closed tuple, so an external catalogue
    would only mirror the same data.

    Attributes:
        due_soon_days: Window before
            :attr:`aeat.domain.deadlines.FilingObligation.closes_on` that
            flags :attr:`aeat.domain.deadlines.ObligationStatus.DUE_SOON`
            (default 14).
    """

    def __init__(
        self,
        *,
        due_soon_days: int = _DEFAULT_DUE_SOON_DAYS,
    ) -> None:
        """Construct an engine.

        Args:
            due_soon_days: Days before ``closes_on`` that flag
                ``DUE_SOON``. Must be ``>= 0``.

        Raises:
            ValueError: If ``due_soon_days`` is negative.
        """
        if due_soon_days < 0:
            raise ValueError(f"due_soon_days must be >= 0, got {due_soon_days}")
        self.due_soon_days = due_soon_days

    def compute(
        self,
        profile: AutonomoProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Compute the full :class:`Schedule` for ``profile`` x ``year``.

        Pure function: no I/O, no input mutation. Identical
        ``(profile, year, today)`` always yields an equal schedule
        (modulo :attr:`Schedule.generated_at`).

        Args:
            profile: The autónomo profile.
            year: The fiscal year to compute for.
            today: Reference date for status classification. Defaults
                to ``date.today()``.

        Returns:
            The :class:`Schedule` containing every obligation that
            applies to ``profile`` for ``year``.

        Raises:
            :exc:`aeat.domain.deadlines.ScheduleComputationError`: If no
                canonical windows are registered for ``year``.
        """
        reference_today = today or date.today()
        windows = _windows_for_year(year)
        if not windows:
            raise ScheduleComputationError(
                f"No canonical windows registered for year {year}; "
                "supported years are derived from aeat.domain.deadlines._calendar.SUPPORTED_YEARS"
            )

        obligations: list[FilingObligation] = []
        for modelo in KNOWN_AUTONOMO_MODELOS:
            if not applies_to(profile, modelo):
                continue
            applies_because = explain(profile, modelo)
            for window in windows:
                if window.modelo != modelo:
                    continue
                obligations.append(
                    FilingObligation(
                        modelo=modelo,
                        period=window.period,
                        opens_on=window.opens_on,
                        closes_on=window.closes_on,
                        payment_cutoff_on=window.payment_cutoff_on,
                        status=_classify(
                            window.closes_on,
                            reference_today,
                            self.due_soon_days,
                        ),
                        applies_because=applies_because,
                        boe_references=window.boe_references,
                    )
                )

        obligations.sort(key=lambda o: (o.closes_on, o.modelo, o.period))
        return Schedule(
            profile=profile,
            year=year,
            obligations=tuple(obligations),
            generated_at=datetime.now(UTC),
        )


def next_deadline(schedule: Schedule, today: date | None = None) -> FilingObligation | None:
    """Return the next obligation in ``schedule`` that has not yet closed.

    Pure function. Returns ``None`` if every obligation in the schedule
    is already overdue (or the schedule is empty).

    Args:
        schedule: The schedule to scan.
        today: Reference date. Defaults to ``date.today()``.

    Returns:
        The earliest non-overdue :class:`FilingObligation`, or ``None``
        if no such obligation exists.
    """
    reference_today = today or date.today()
    upcoming = [o for o in schedule.obligations if o.closes_on >= reference_today]
    if not upcoming:
        return None
    upcoming.sort(key=lambda o: (o.closes_on, o.modelo, o.period))
    return upcoming[0]
