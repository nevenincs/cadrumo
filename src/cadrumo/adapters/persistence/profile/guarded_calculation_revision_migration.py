"""Guarded calculation-revision migration capability with execution-owned rekeying."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....application.modelo.projection_migration_ports import ProjectionMigrationPlan

if TYPE_CHECKING:
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation
    from ....domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol


class GuardedCalculationRevisionMigration:
    """Prepare legacy override rekeying outside COMMIT, then publish by CAS."""

    def prepare(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        *,
        operation: PinnedAuthorityOperation,
    ) -> ProjectionMigrationPlan:
        """Return a pure full-catalogue plan tied to the observed row revision."""
        from .calculation_revision_override_migration import rekey_calculation_revision_overrides

        catalogue, expected_revision_id = repository.load_revisioned(operation=operation)
        result = rekey_calculation_revision_overrides(catalogue, operation=operation)
        return ProjectionMigrationPlan(
            catalogue=result.catalogue,
            expected_revision_id=expected_revision_id,
            changed=result.changed,
            revision_id_pairs=tuple(
                (remap.previous_calculation_revision_id, remap.calculation_revision_id)
                for remap in result.rekeyed_revisions
            ),
            override_key_pairs=tuple(
                (str(move.relation_id), str(move.binding_id)) for move in result.rekeyed_override_keys
            ),
        )

    def commit(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        plan: ProjectionMigrationPlan,
    ) -> None:
        """Publish exactly the prepared catalogue or propagate the CAS conflict."""
        if not plan.changed:
            raise ValueError("an unchanged calculation catalogue has no migration write")
        repository.save_with_secure_object_writes(
            plan.catalogue,
            (),
            expected_revision_id=plan.expected_revision_id,
        )

    def assert_current(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        *,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Refuse a concurrent legacy addition without running a hidden write."""
        from ....domain.modelos.calculation_repository import CalculationRevisionPersistenceError
        from .calculation_revision_override_migration import _MIGRATION_MESSAGE, rekey_calculation_revision_overrides

        catalogue = repository.load(operation=operation)
        if rekey_calculation_revision_overrides(catalogue, operation=operation).changed:
            raise CalculationRevisionPersistenceError(
                "calculation revisions changed after migration preparation",
                translated_message=_MIGRATION_MESSAGE,
                context={"reason": "relation_override_migration_required_after_preparation"},
            )


__all__ = ["GuardedCalculationRevisionMigration"]
