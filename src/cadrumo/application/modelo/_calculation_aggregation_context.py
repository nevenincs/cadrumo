"""Context loading for bucket-aggregation calculation actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.authority_grade import RegistryAuthorityGrade
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ._calculation_helpers import resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit
from .profile_readiness_gate import require_profile_ready_for_work_unit
from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.modelos.work_unit import WorkUnit


def load_bucket_aggregation_context(
    work_unit_id: str,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    profile: ModeloWorkProfile | None,
) -> tuple[WorkUnit, RegistrySnapshot, ModeloWorkProfile]:
    """Return ``(work_unit, snapshot, profile)`` for aggregation calculation.

    ``profile`` is the record the calling command already loaded, or ``None``
    for the gate to load it; either way the returned profile is the one the
    readiness gate checked, and it is the only profile the calculation reads.
    """
    work_units = work_unit_repository.load()
    work_unit = require_active_work_unit(
        work_units,
        work_unit_id=work_unit_id,
        repository_bucket_id=work_unit_repository.bucket_id,
        use=ActiveWorkUnitUse.CALCULATE,
    )
    from ...domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        checked_profile = require_profile_ready_for_work_unit(
            work_unit,
            profile_decode_context=operation.profile_decode_context(),
            operation=operation,
            profile=profile,
        )

        # The calculate path needs the rung that computes amounts, not the filing
        # rung: a revision that honestly declares calculation must not be refused
        # for work this application does entirely in memory. The work unit is held
        # for ``ActiveWorkUnitUse.CALCULATE`` and no fichero or export layout is
        # rendered here, so the filing rung would be an authority this path never
        # exercises -- and demanding it makes a deliberate calculation-grade
        # revision uncalculable, not merely unfilable.
        snapshot = _resolve_registry_snapshot_for_work_unit(
            work_unit,
            grade=RegistryAuthorityGrade.CALCULATION,
            operation=operation,
        )
        return work_unit, snapshot, checked_profile


__all__ = ["load_bucket_aggregation_context"]
