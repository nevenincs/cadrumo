"""The narrow persisted-revision migration capability for modelo projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
    from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol


@dataclass(frozen=True, slots=True)
class ProjectionMigrationPlan:
    """One pure, revision-guarded preparation of the full stored catalogue."""

    catalogue: CalculationRevisionCatalogue
    expected_revision_id: str
    changed: bool
    revision_id_pairs: tuple[tuple[str, str], ...] = ()
    override_key_pairs: tuple[tuple[str, str], ...] = ()


class ProjectionMigrationPort(Protocol):
    """Separate full-catalogue preparation from its single guarded write."""

    def prepare(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        *,
        operation: PinnedAuthorityOperation,
    ) -> ProjectionMigrationPlan:
        """Read and rekey in memory, preserving the current row revision."""
        ...

    def commit(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        plan: ProjectionMigrationPlan,
    ) -> None:
        """Publish a changed plan with one guarded repository write."""
        ...

    def assert_current(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        *,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Refuse a new legacy revision during subsequent recorded reads."""
        ...


__all__ = ["ProjectionMigrationPlan", "ProjectionMigrationPort"]
