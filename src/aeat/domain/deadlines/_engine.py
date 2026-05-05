"""Registry-backed deadline computation engine.

Takes an :class:`AutonomoProfile` and a year and produces a deterministic,
typed :class:`Schedule`. Filing windows and applicability conditions are
read from validated calculation registry data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from ...core.logging import get_logger
from ...core.paths import PROJECT_ROOT
from ..calculations.registry import (
    DeadlineApplicabilityCondition,
    DeadlineWindowDefinition,
    RegistryError,
    RegistryValidator,
    evaluate_profile_conditions,
    load_registry_tree,
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
_DEFAULT_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


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
            ValueError: If ``due_soon_days`` is negative.
            ScheduleComputationError: If registry loading or validation fails.
        """
        if due_soon_days < 0:
            raise ValueError(f"due_soon_days must be >= 0, got {due_soon_days}")
        self.due_soon_days = due_soon_days
        self._source_root = source_root or PROJECT_ROOT
        root = registry_root or _DEFAULT_REGISTRY_ROOT
        try:
            self._modelos, self._catalogues = load_registry_tree(root)
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
        for modelo, window in self._deadline_windows(year):
            condition_text = self._evaluate_conditions(
                profile,
                window.applicability_conditions,
                mode=window.applicability_condition_mode,
            )
            if condition_text is None:
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
                    applies_because=condition_text,
                    boe_references=window.legal_refs,
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
        windows = [window for code, window in self._deadline_windows(selected_year) if code == modelo]
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
            and self._evaluate_conditions(
                profile,
                window.applicability_conditions,
                mode=window.applicability_condition_mode,
            )
            is not None
            for code, window in self._deadline_windows(selected_year)
        )

    def _deadline_windows(self, year: int) -> tuple[tuple[str, DeadlineWindowDefinition], ...]:
        out: list[tuple[str, DeadlineWindowDefinition]] = []
        for modelo in self._modelos:
            try:
                RegistryValidator(self._catalogues, source_root=self._source_root).validate_modelo(modelo)
            except RegistryError as exc:
                message = f"deadline registry validation failed for modelo {modelo.id}: {exc}"
                raise ScheduleComputationError(message) from exc
            for revision in modelo.revisions.values():
                for window in revision.deadline_windows:
                    if window.filing_year == year:
                        out.append((modelo.id, window))
        out.sort(key=lambda item: (item[1].closes_on, item[0], item[1].period))
        return tuple(out)

    def _has_deadline_windows(self, year: int) -> bool:
        return bool(self._deadline_windows(year))

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
