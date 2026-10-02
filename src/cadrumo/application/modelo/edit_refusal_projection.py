"""Apply-specific calculation prerequisites retained only for the submitting session.

The operation journal retains its registered refusal family, never these
addresses. A TUI session may register the exact renewed baseline before
starting its operation and consume this bounded projection once afterwards.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.ids import BindingId
from .edit_models import ModeloEditBaselineV1


@dataclass(frozen=True, slots=True)
class ModeloEditCalculationPrerequisiteV1:
    """One unresolved calculation source, with no raw exception or entered value."""

    operation_id: str
    work_unit_id: str
    baseline_id: str
    calculation_revision_id: str | None
    casilla_id: CasillaId
    binding_ids: tuple[BindingId, ...]


type ModeloEditPrerequisiteObserver = Callable[[ModeloEditCalculationPrerequisiteV1], None]


class ModeloEditRefusalProjectionStore:
    """Bounded private memory owned and cleared by one installed session."""

    def __init__(self) -> None:
        """Start without any submitted operation or diagnostic."""
        self._expected: dict[str, tuple[str, str, str | None]] = {}
        self._prerequisites: dict[str, ModeloEditCalculationPrerequisiteV1] = {}

    def expect(self, operation_id: str, baseline: ModeloEditBaselineV1) -> None:
        """Bind delivery to the actual renewed baseline used by this Apply."""
        if len(self._expected) >= 16:
            oldest = next(iter(self._expected))
            self._expected.pop(oldest)
            self._prerequisites.pop(oldest, None)
        self._expected[operation_id] = (
            str(baseline.work_unit_id),
            str(baseline.baseline_id),
            baseline.current_calculation_revision_id,
        )
        self._prerequisites.pop(operation_id, None)

    def observe(self, prerequisite: ModeloEditCalculationPrerequisiteV1) -> None:
        """Retain only the registered operation's exact baseline and work coordinate."""
        expected = (prerequisite.work_unit_id, prerequisite.baseline_id, prerequisite.calculation_revision_id)
        if self._expected.get(prerequisite.operation_id) == expected:
            self._prerequisites[prerequisite.operation_id] = prerequisite

    def take(
        self, operation_id: str, *, work_unit_id: str, calculation_revision_id: str | None
    ) -> ModeloEditCalculationPrerequisiteV1 | None:
        """Consume once; discard stale, successful or canceled operation context too."""
        expected = self._expected.pop(operation_id, None)
        prerequisite = self._prerequisites.pop(operation_id, None)
        if expected is None or expected[0] != work_unit_id or expected[2] != calculation_revision_id:
            return None
        return prerequisite

    def clear(self) -> None:
        """Drop all private delivery context when the session closes."""
        self._expected.clear()
        self._prerequisites.clear()


__all__ = [
    "ModeloEditCalculationPrerequisiteV1",
    "ModeloEditPrerequisiteObserver",
    "ModeloEditRefusalProjectionStore",
]
