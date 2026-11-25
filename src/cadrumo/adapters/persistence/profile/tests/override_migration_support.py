"""Transaction catalogue shared by the override migration suites."""

from __future__ import annotations

from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
)


def override_migration_catalogue(revision: CalculationRevision) -> CalculationRevisionCatalogue:
    return CalculationRevisionCatalogue(revisions={revision.calculation_revision_id: revision})
