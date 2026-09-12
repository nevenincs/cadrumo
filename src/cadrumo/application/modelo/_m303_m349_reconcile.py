"""Registry-owned cross-model reconciliation extension point.

The declaration data for this advisory belongs to the versioned Modelo 303
and Modelo 349 registry surfaces. This module keeps only the application
extension point and consumes the selected registry declarations.
"""

from __future__ import annotations

from ...domain.calculations.registry.schema_verification import VerificationExpectationDefinition
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.verification_report import ModeloVerificationFinding
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol


def _selected_registry_reconciliation_expectations(
    work_unit: WorkUnit,
) -> tuple[VerificationExpectationDefinition, ...]:
    """Read reconciliation declarations from the work unit's selected registry snapshot."""
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

    snapshot = resolve_registry_snapshot_for_work_unit(work_unit)
    return tuple(
        expectation
        for expectation in snapshot.revision.verification_expectations
        if expectation.reconcile_when_present_casilla_ids or expectation.reconciliation_total_casilla_ids
    )


def m303_m349_intracom_reconcile_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
) -> list[ModeloVerificationFinding]:
    # fact-relocation: registry verification expectation consumption is active
    _selected_registry_reconciliation_expectations(work_unit)
    del target, work_unit_repository, calculation_repository
    return []


__all__ = ["m303_m349_intracom_reconcile_findings"]
