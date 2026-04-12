"""Pure-function deadline computation engine.

The engine takes an :class:`AutonomoProfile` and a year and produces a
deterministic, typed :class:`Schedule`. It performs **no I/O** after
construction, never mutates inputs, and never reaches for global
state. The same ``(profile, year, today)`` always yields an equal
schedule (modulo :attr:`Schedule.generated_at`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from aeat.deadlines._applies import applies_to, explain
from aeat.deadlines._calendar import (
    CALENDAR,
    KNOWN_AUTONOMO_MODELOS,
    CanonicalWindow,
)
from aeat.deadlines._errors import ScheduleComputationError
from aeat.deadlines._models import (
    AutonomoProfile,
    FilingObligation,
    ObligationStatus,
    Schedule,
)
from aeat.deadlines._protocols import (
    CorpusReader,
    ModeloCatalogueLoader,
    ModeloIdentifier,
)
from aeat.logging import get_logger

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

    The engine is stateless after construction. It accepts a
    Protocol-stubbed catalogue loader and an optional Protocol-stubbed
    corpus reader so it can compile and ship before its upstream
    subpackages (#6 ``aeat.models``, #17 ``aeat.corpus``) land on
    ``main``.

    Attributes:
        catalogue: The :class:`ModeloCatalogueLoader` used to validate
            that emitted obligations reference known modelos.
        corpus: Optional :class:`CorpusReader` for year-specific window
            overrides. ``None`` falls back to the in-code calendar.
        due_soon_days: Window before ``closes_on`` that flags
            ``DUE_SOON`` (default 14).
    """

    def __init__(
        self,
        catalogue: ModeloCatalogueLoader,
        *,
        corpus: CorpusReader | None = None,
        due_soon_days: int = _DEFAULT_DUE_SOON_DAYS,
    ) -> None:
        """Construct an engine.

        Args:
            catalogue: The catalogue loader Protocol implementation.
            corpus: Optional corpus reader Protocol implementation.
            due_soon_days: Days before ``closes_on`` that flag
                ``DUE_SOON``. Must be ``>= 0``.

        Raises:
            ValueError: If ``due_soon_days`` is negative.
        """
        if due_soon_days < 0:
            raise ValueError(f"due_soon_days must be >= 0, got {due_soon_days}")
        self.catalogue = catalogue
        self.corpus = corpus
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
            ScheduleComputationError: If no canonical windows are
                registered for ``year``.
        """
        reference_today = today or date.today()
        windows = _windows_for_year(year)
        if not windows:
            raise ScheduleComputationError(
                f"No canonical windows registered for year {year}; "
                "supported years are derived from aeat.deadlines._calendar.SUPPORTED_YEARS"
            )

        # Optional corpus consultation. The Protocol's return type is
        # opaque (Any) until #17 lands; v1 logs that overrides were
        # observed but does not yet apply them.
        if self.corpus is not None:
            overrides = self.corpus.load_year_overrides(year)
            if overrides:
                _logger.debug(
                    "corpus reader returned %d overrides for %d; v1 engine ignores them",
                    len(overrides),
                    year,
                )

        obligations: list[FilingObligation] = []
        for modelo in KNOWN_AUTONOMO_MODELOS:
            if not self.catalogue.is_known(ModeloIdentifier(modelo)):
                _logger.debug("modelo %s not in catalogue; skipping in compute()", modelo)
                continue
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
