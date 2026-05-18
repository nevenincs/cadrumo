"""Registry-backed deadline computation engine.

Takes an :class:`AutonomoProfile` and a year and produces a deterministic,
typed :class:`Schedule`. Filing windows and applicability conditions are
read from validated calculation registry data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from ...core.logging import get_logger
from ...core.resources import bundled_path
from ..calculations.registry import (
    DeadlineApplicabilityCondition,
    DeadlineWindowDefinition,
    ModeloRevision,
    RegistryError,
    ValidatedRegistryAuthority,
    applicable_filing_schedules,
    evaluate_profile_conditions,
)
from ._errors import DeadlineValidationError, ScheduleComputationError
from ._models import (
    AutonomoProfile,
    FilingObligation,
    ObligationStatus,
    Schedule,
)
from ._recargo import build_recovery_for_overdue

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


def _window_outside_activity_period(
    *,
    opens_on: date,
    closes_on: date,
    activity_start_date: date | None,
    activity_end_date: date | None,
) -> bool:
    """Return True when an AEAT window falls entirely outside the
    operator's census-declared activity period.

    Two gates, both grounded in RGAT Arts. 9 / 11 (census activity
    start / end dates published on G313):

    * Pre-start: ``closes_on < activity_start_date`` — the entire
      window precedes the alta. AEAT does not expect a filing for
      activity that did not occur.
    * Post-baja: ``opens_on > activity_end_date`` — the entire window
      follows the baja. AEAT does not expect a forward-period filing
      after the operator has declared baja.

    Windows that straddle either date stay on the schedule — the
    operator may still owe a return covering the active fraction.
    """

    if activity_start_date is not None and closes_on < activity_start_date:
        return True
    if activity_end_date is not None and opens_on > activity_end_date:
        return True
    return False


class DeadlineEngine:
    """Engine that computes typed filing schedules from registry data.

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
        registry_root: Path | None = None,
        source_root: Path | None = None,
    ) -> None:
        """Construct an engine.

        Args:
            due_soon_days: Days before ``closes_on`` that flag
                ``DUE_SOON``. Must be ``>= 0``.
            registry_root: Root containing reviewed registry TOML files.
            source_root: Repository root for source-integrity checks.

        Raises:
            DeadlineValidationError: If ``due_soon_days`` is negative.
            ScheduleComputationError: If registry loading or validation fails.
        """
        if due_soon_days < 0:
            raise DeadlineValidationError(f"due_soon_days must be >= 0, got {due_soon_days}")
        self.due_soon_days = due_soon_days
        if registry_root is None and source_root is None:
            from ...core.resources import resources

            self._registry = resources().modelos.authority
            self._source_root = bundled_path()
            return
        self._source_root = source_root if source_root is not None else bundled_path()
        root = registry_root if registry_root is not None else bundled_path("registry", "aeat")
        try:
            self._registry = ValidatedRegistryAuthority.load(root, source_root=self._source_root)
        except RegistryError as exc:
            raise ScheduleComputationError(f"deadline registry load failed: {exc}") from exc

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
                validated registry deadline windows apply to ``year``.
        """
        reference_today = today or date.today()
        _logger.debug("computing schedule year=%d reference_today=%s", year, reference_today)
        obligations: list[FilingObligation] = []
        for modelo, revision, window in self._deadline_windows(year):
            registry_period = _window_registry_period(window)
            if revision.filing_schedules and not applicable_filing_schedules(
                revision,
                profile,
                period=registry_period,
            ):
                continue
            condition_text = self._evaluate_conditions(
                profile,
                window.applicability_conditions,
                mode=window.applicability_condition_mode,
            )
            if condition_text is None:
                continue
            if _window_outside_activity_period(
                opens_on=window.opens_on,
                closes_on=window.closes_on,
                activity_start_date=profile.activity_start_date,
                activity_end_date=profile.activity_end_date,
            ):
                continue
            obligation_status = _classify(
                window.closes_on,
                reference_today,
                self.due_soon_days,
            )
            recovery = None
            if obligation_status is ObligationStatus.OVERDUE:
                days_late = (reference_today - window.closes_on).days
                if days_late >= 1:
                    try:
                        recovery = build_recovery_for_overdue(
                            days_late=days_late,
                            modelo=modelo,
                            period=window.period,
                        )
                    except (FileNotFoundError, ValueError):
                        recovery = None
            obligations.append(
                FilingObligation(
                    modelo=modelo,
                    period=window.period,
                    opens_on=window.opens_on,
                    closes_on=window.closes_on,
                    payment_cutoff_on=window.payment_cutoff_on,
                    status=obligation_status,
                    applies_because=condition_text,
                    boe_references=window.legal_refs,
                    recovery=recovery,
                )
            )

        obligations.sort(key=lambda o: (o.closes_on, o.modelo, o.period))
        if not obligations and not self._has_deadline_windows(year):
            raise ScheduleComputationError(f"No registry deadline windows registered for year {year}")
        if obligations:
            _logger.debug("computed schedule year=%d obligations=%d", year, len(obligations))
        else:
            _logger.debug("no filing obligations computed year=%d: profile conditions did not match", year)
        return Schedule(
            profile=profile,
            year=year,
            obligations=tuple(obligations),
            generated_at=datetime.now(UTC),
        )

    def explain(self, profile: AutonomoProfile, modelo: str, *, year: int | None = None) -> str:
        """Return registry-backed deadline applicability text for ``modelo``."""

        selected_year = year or date.today().year
        windows = [
            window
            for code, revision, window in self._deadline_windows(selected_year)
            if code == modelo and self._schedule_applies(profile, revision, window)
        ]
        if not windows:
            raise ScheduleComputationError(
                f"No registry deadline windows registered for modelo {modelo!r} in year {selected_year}"
            )
        condition_text = self._evaluate_conditions(
            profile,
            windows[0].applicability_conditions,
            mode=windows[0].applicability_condition_mode,
        )
        if condition_text is None:
            return "No aplica segun las condiciones registrales del modelo."
        return condition_text

    def applies_to(self, profile: AutonomoProfile, modelo: str, *, year: int | None = None) -> bool:
        """Return whether registry deadline conditions match for ``modelo``."""

        selected_year = year or date.today().year
        return any(
            code == modelo
            and self._schedule_applies(profile, revision, window)
            and self._evaluate_conditions(
                profile,
                window.applicability_conditions,
                mode=window.applicability_condition_mode,
            )
            is not None
            for code, revision, window in self._deadline_windows(selected_year)
        )

    def _deadline_windows(self, year: int) -> tuple[tuple[str, ModeloRevision, DeadlineWindowDefinition], ...]:
        try:
            return self._registry.deadline_windows(year)
        except RegistryError as exc:
            raise ScheduleComputationError(f"deadline registry validation failed: {exc}") from exc

    def _has_deadline_windows(self, year: int) -> bool:
        return bool(self._deadline_windows(year))

    @staticmethod
    def _schedule_applies(profile: AutonomoProfile, revision: ModeloRevision, window: DeadlineWindowDefinition) -> bool:
        if not revision.filing_schedules:
            return True
        return bool(applicable_filing_schedules(revision, profile, period=_window_registry_period(window)))

    @staticmethod
    def _evaluate_conditions(
        profile: AutonomoProfile,
        conditions: tuple[DeadlineApplicabilityCondition, ...],
        *,
        mode: str,
    ) -> str | None:
        if not conditions:
            return "Aplica segun la ventana registral del modelo."
        try:
            explanations = evaluate_profile_conditions(conditions, profile, mode=mode)
        except RegistryError as exc:
            raise ScheduleComputationError(f"deadline profile condition could not be evaluated: {exc}") from exc
        if explanations is None:
            return None
        return " ".join(explanations)


def _window_registry_period(window: DeadlineWindowDefinition) -> str:
    if window.period_kind == "quarterly" and "Q" in window.period:
        return f"{window.period.rsplit('Q', 1)[1]}T"
    if window.period_kind == "quarterly" and window.period.endswith("T"):
        return window.period.rsplit("-", 1)[-1]
    if window.period_kind == "monthly" and "-" in window.period:
        return window.period.rsplit("-", 1)[1]
    if window.period_kind == "annual":
        return "0A"
    return window.period


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


def applies_to(profile: AutonomoProfile, modelo: str) -> bool:
    """Return whether registry deadline conditions match for ``modelo``."""

    return DeadlineEngine().applies_to(profile, modelo)


def explain(profile: AutonomoProfile, modelo: str) -> str:
    """Return registry-backed deadline applicability text for ``modelo``."""

    return DeadlineEngine().explain(profile, modelo)
