"""Apply-specific calculation prerequisites held only inside the profile worker.

The operation journal retains its registered refusal family, never these
addresses. The worker that ran a refused Apply retains the prerequisite it
named, bounded and in memory only, and hands it out once to a read that names
the same operation, work unit, renewed baseline and calculation head.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Final

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.ids import BindingId

_RETAINED_LIMIT: Final[int] = 16
"""Refused Applies whose prerequisite stays readable; older ones are forgotten first."""


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
    """Bounded private memory of the prerequisites refused Applies named in this worker."""

    def __init__(self) -> None:
        """Start without any retained diagnostic."""
        self._lock = Lock()
        self._prerequisites: dict[str, ModeloEditCalculationPrerequisiteV1] = {}

    def retain(self, prerequisite: ModeloEditCalculationPrerequisiteV1) -> None:
        """Keep one refused Apply's prerequisite, forgetting the oldest beyond the bound."""
        with self._lock:
            self._prerequisites.pop(prerequisite.operation_id, None)
            if len(self._prerequisites) >= _RETAINED_LIMIT:
                self._prerequisites.pop(next(iter(self._prerequisites)))
            self._prerequisites[prerequisite.operation_id] = prerequisite

    def take(
        self,
        operation_id: str,
        *,
        work_unit_id: str,
        baseline_id: str,
        calculation_revision_id: str | None,
    ) -> ModeloEditCalculationPrerequisiteV1 | None:
        """Consume once; a read naming any other coordinate discards it unread."""
        with self._lock:
            prerequisite = self._prerequisites.pop(operation_id, None)
        if prerequisite is None or (
            prerequisite.work_unit_id,
            prerequisite.baseline_id,
            prerequisite.calculation_revision_id,
        ) != (work_unit_id, baseline_id, calculation_revision_id):
            return None
        return prerequisite


__all__ = [
    "ModeloEditCalculationPrerequisiteV1",
    "ModeloEditPrerequisiteObserver",
    "ModeloEditRefusalProjectionStore",
]
