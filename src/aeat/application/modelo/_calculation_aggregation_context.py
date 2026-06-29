"""Context loading for bucket-aggregation calculation actions."""

from __future__ import annotations

from ...domain.calculations.registry import RegistrySnapshotError
from ...domain.modelos._protocols import WorkUnitCatalogueRepositoryProtocol
from ...domain.modelos._work_unit import WorkUnitState
from ._action_errors import (
    CalculationRegistryUnavailableError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    WorkUnitRevisionDivergenceError,
)
from ._profile_readiness_gate import require_profile_ready_for_work_unit
from ._registry_resources import authority_via_resources as _authority_via_resources
from ._registry_resources import registry_root as _registry_root


def load_bucket_aggregation_context(
    work_unit_id: str,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
):
    """Return ``(work_unit, snapshot)`` for aggregation calculation."""
    work_units = work_unit_repository.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_discarded_cannot_calculate",
            context={"work_unit_id": work_unit_id},
        )
    require_profile_ready_for_work_unit(work_unit)

    try:
        authority = _authority_via_resources()
        snapshot = authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_root_missing",
            context={"registry_root": _registry_root()},
        ) from exc
    except RegistrySnapshotError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_snapshot_unresolved",
            context={
                "modelo": work_unit.modelo,
                "filing_year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
            },
        ) from exc
    if snapshot.revision.id != work_unit.revision_id:
        raise WorkUnitRevisionDivergenceError(
            f"work unit {work_unit.work_unit_id!r} was created against registry revision "
            f"{work_unit.revision_id!r}, but the law-determined revision for "
            f"modelo {work_unit.modelo!r} {work_unit.filing_year} {work_unit.period.registry_token!r} "
            f"is now {snapshot.revision.id!r}. "
            f"The registry's law-mapping was corrected after this work unit was created. "
            f"Re-create the work unit (discard this one and run `aeat app modelo work create`) "
            f"to bind it to the current law-determined revision.",
        )
    return work_unit, snapshot


__all__ = ["load_bucket_aggregation_context"]
