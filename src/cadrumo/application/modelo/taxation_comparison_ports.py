"""Application-owned read capability for Modelo taxation comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.modelos.work_unit import WorkUnitCatalogue


class TaxationComparisonPersistenceError(RuntimeError):
    """Translated failure while loading work units for taxation comparison."""

    def __init__(self, operation: str) -> None:
        """Carry the application operation without exposing storage details."""
        self.operation = operation
        super().__init__(f"taxation comparison persistence operation failed: {operation}")


class TaxationComparisonWorkUnitReader(Protocol):
    """Read capability for the bucket-bound work-unit comparison projection."""

    def load(self) -> WorkUnitCatalogue:
        """Return the validated work-unit catalogue for the composed bucket."""
        ...


@dataclass(frozen=True, slots=True)
class TaxationComparisonPorts:
    """Required capability bundle for one taxation comparison invocation."""

    work_unit_reader: TaxationComparisonWorkUnitReader


__all__ = [
    "TaxationComparisonPersistenceError",
    "TaxationComparisonPorts",
    "TaxationComparisonWorkUnitReader",
]
