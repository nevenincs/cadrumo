"""The actual calculation write and its atomically selected parent snapshot."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit


@dataclass(frozen=True, slots=True)
class CalculationRevisionPublication:
    """Witness the revision/pointer transaction, including duplicate writes.

    ``published`` covers this transaction's revision, parent pointer, event and
    caller-supplied co-writes. It does not describe separate prerequisite writes
    performed earlier by the calculation service.
    """

    revision: CalculationRevision
    work_unit: WorkUnit
    published: bool

    def __post_init__(self) -> None:
        """Keep the returned revision bound to the observed or committed parent."""
        if self.revision.work_unit_id != self.work_unit.work_unit_id:
            raise ValueError("calculation publication belongs to a different work unit")


__all__ = ["CalculationRevisionPublication"]
