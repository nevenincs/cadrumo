"""Context loading for bucket-aggregation calculation actions."""

from __future__ import annotations

from ...core.authority_grade import RegistryAuthorityGrade
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit
from ._profile_readiness_gate import require_profile_ready_for_work_unit
from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit


def load_bucket_aggregation_context(
    work_unit_id: str,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
):
    """Return ``(work_unit, snapshot)`` for aggregation calculation."""
    work_units = work_unit_repository.load()
    work_unit = require_active_work_unit(
        work_units,
        work_unit_id=work_unit_id,
        repository_bucket_id=work_unit_repository.bucket_id,
        use=ActiveWorkUnitUse.CALCULATE,
    )
    require_profile_ready_for_work_unit(work_unit)

    # The calculate path needs the rung that computes amounts, not the filing
    # rung: a revision that honestly declares calculation must not be refused
    # for work this application does entirely in memory. The work unit is held
    # for ``ActiveWorkUnitUse.CALCULATE`` and no fichero or export layout is
    # rendered here, so the filing rung would be an authority this path never
    # exercises -- and demanding it makes a deliberate calculation-grade
    # revision uncalculable, not merely unfilable.
    return work_unit, _resolve_registry_snapshot_for_work_unit(
        work_unit,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


__all__ = ["load_bucket_aggregation_context"]
