"""A BORRADOR calculation revision that carries only its source provenance."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_sources import CalculationSourceRef
from ....domain.modelos.work_unit import WorkUnit


def empty_borrador_revision(
    work_unit: WorkUnit,
    snapshot_ref: RegistrySnapshotRef,
    source_provenance: Sequence[CalculationSourceRef],
    *,
    at: datetime,
) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=source_provenance,
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        observations=(),
        created_at=at,
        updated_at=at,
        filing_instance_evidence=None,
        source_provenance=source_provenance,
    )
