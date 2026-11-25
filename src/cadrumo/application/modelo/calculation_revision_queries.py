"""Read calculation revisions from their owning repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.identity.hex_ids import CalculationRevisionId
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
)
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .action_errors import (
    CalculationRevisionNotFoundError,
)
from .calculation_action_ports import (
    CalculationActionPorts,
)
from .calculation_revision_gate import require_calculation_revision_coordinates_current

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def list_calculation_revisions(
    *,
    ports: CalculationActionPorts,
    work_unit_id: str | None = None,
) -> tuple[CalculationRevision, ...]:
    """List calculation revisions, optionally filtered to one work unit.

    Results are sorted by ``(work_unit_id, created_at)`` so the
    chronological revision chain for one work unit is contiguous
    and stable across calls.

    Each element is a :class:`CalculationRevision`.
    """
    ports.relation_override_migration.migrate(ports.calculation_repository, operation=ports.operation)
    catalogue = ports.calculation_repository.load(operation=ports.operation)
    revisions = tuple(
        revision for revision in catalogue if work_unit_id is None or revision.work_unit_id == work_unit_id
    )
    for revision in revisions:
        require_calculation_revision_coordinates_current(revision, operation=ports.operation)
    return tuple(sorted(revisions, key=lambda r: (r.work_unit_id, r.created_at)))


def get_calculation_revision(
    calculation_revision_id: CalculationRevisionId,
    *,
    ports: CalculationActionPorts,
) -> CalculationRevision:
    """Return one calculation revision by id, or raise.

    Returns the :class:`CalculationRevision` matching
    ``calculation_revision_id``.
    """
    ports.relation_override_migration.migrate(ports.calculation_repository, operation=ports.operation)
    return get_recorded_calculation_revision(calculation_revision_id, ports=ports)


def get_recorded_calculation_revision(
    calculation_revision_id: CalculationRevisionId,
    *,
    ports: CalculationActionPorts,
) -> CalculationRevision:
    """Read current persisted coordinates without migrating or changing storage.

    Read-only operations use this door so an unsupported persisted revision
    refuses through the canonical coordinate gate before any domain write.
    """
    revision, _ = _calculation_revision_in_repository_bucket(
        calculation_revision_id,
        catalogue=ports.calculation_repository.load(operation=ports.operation),
        calculation_repository=ports.calculation_repository,
        work_unit_repository=ports.work_unit_repository,
        operation=ports.operation,
    )
    return revision


def _calculation_revision_in_repository_bucket(
    calculation_revision_id: CalculationRevisionId,
    *,
    catalogue: CalculationRevisionCatalogue,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationRevision, WorkUnit]:
    """Resolve a revision only when its work unit belongs to both repositories' bucket."""
    revision = catalogue.get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    require_calculation_revision_coordinates_current(revision, operation=operation)
    work_unit = work_unit_repository.load().get(revision.work_unit_id)
    expected_buckets = {
        bucket_id
        for bucket_id in (calculation_repository.bucket_id, work_unit_repository.bucket_id)
        if bucket_id is not None
    }
    if work_unit is None or any(work_unit.bucket_id != bucket_id for bucket_id in expected_buckets):
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    return revision, work_unit
