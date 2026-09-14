"""Registry-owned cross-model reconciliation extension point.

The declaration data for this advisory belongs to the versioned registry
surfaces.  This module keeps only generic work-unit selection, persisted-value
reading, arithmetic, and finding construction.  The paired models, operand
casillas, tolerance, and provenance are all discovered from the selected
verification expectations; none is copied into Python.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_verification import VerificationExpectationDefinition
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .work_selection import (
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    select_modelo_work_resolution,
)


class _ReconciliationContract(NamedTuple):
    """One registry-declared expectation paired with its counterpart."""

    expectation: VerificationExpectationDefinition
    sibling_modelo: str
    sibling_expectation: VerificationExpectationDefinition


def _selected_registry_reconciliation_context(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[RegistrySnapshot, tuple[VerificationExpectationDefinition, ...]]:
    """Return the pinned snapshot and its selected reconciliation expectations.

    ``describe_modelo_for_scope`` is deliberately checked against the
    work-unit snapshot.  A divergent query result is a closed result rather
    than permission to use an unselected registry revision.
    """
    from ._calculation_helpers import assert_snapshot_matches_work_unit_revision

    snapshot = operation.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    assert_snapshot_matches_work_unit_revision(work_unit, snapshot)
    try:
        selected_revision = operation.revision_for_context(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except (RegistrySnapshotError, RegistryValidationError):
        return snapshot, ()
    if str(selected_revision.id) != str(snapshot.revision.id):
        return snapshot, ()
    expectations = tuple(
        expectation
        for expectation in snapshot.revision.verification_expectations
        if expectation.reconcile_when_present_casilla_ids or expectation.reconciliation_total_casilla_ids
    )
    return snapshot, expectations


def _selected_registry_reconciliation_expectations(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[VerificationExpectationDefinition, ...]:
    """Read reconciliation declarations from the work unit's selected registry snapshot."""
    _snapshot, expectations = _selected_registry_reconciliation_context(work_unit, operation=operation)
    return expectations


def _expectations_are_counterparts(
    left: VerificationExpectationDefinition,
    right: VerificationExpectationDefinition,
) -> bool:
    """Recognise one reciprocal cross-model contract without naming its facts."""
    if not left.reconcile_when_present_casilla_ids or not right.reconcile_when_present_casilla_ids:
        return False
    if left.computed_casilla_ids or right.computed_casilla_ids:
        return False
    if left.reconciliation_total_casilla_ids or right.reconciliation_total_casilla_ids:
        return False
    if Decimal(left.tolerance) != Decimal(right.tolerance):
        return False
    if str(left.rounding) != str(right.rounding):
        return False
    if Decimal(left.min_coverage) != Decimal(right.min_coverage):
        return False
    if tuple(sorted(str(cause) for cause in left.discrepancy_causes)) != tuple(
        sorted(str(cause) for cause in right.discrepancy_causes)
    ):
        return False
    if frozenset(str(ref) for ref in left.legal_refs) != frozenset(str(ref) for ref in right.legal_refs):
        return False
    # Reciprocal source references are the registry's cross-surface identity;
    # requiring an intersection prevents pairing unrelated expectations that
    # happen to share a tolerance and legal vocabulary.
    return bool(frozenset(str(ref) for ref in left.source_refs) & frozenset(str(ref) for ref in right.source_refs))


def _selected_reconciliation_contract(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> _ReconciliationContract | None:
    """Resolve the unique counterpart declared by the live registry."""
    snapshot, expectations = _selected_registry_reconciliation_context(work_unit, operation=operation)
    if not expectations:
        return None

    selected_modelo = str(snapshot.modelo.id)
    matches: list[_ReconciliationContract] = []
    for expectation in expectations:
        counterpart_matches: list[tuple[str, VerificationExpectationDefinition]] = []
        # This is a deliberate registry-wide metadata inventory: the
        # counterpart is not a hard-coded model relationship.  Enumerate only
        # canonical model identifiers, then point-select each candidate's
        # revision for the work-unit coordinate; never hydrate or traverse a
        # sibling's complete revision graph here.
        for sibling_modelo in operation.modelo_ids():
            if sibling_modelo == selected_modelo:
                continue
            try:
                sibling_revision = operation.revision_for_context(
                    sibling_modelo,
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                )
            except (RegistrySnapshotError, RegistryValidationError):
                continue
            counterpart_matches.extend(
                (sibling_modelo, sibling_expectation)
                for sibling_expectation in sibling_revision.verification_expectations
                if _expectations_are_counterparts(expectation, sibling_expectation)
            )
        if len(counterpart_matches) == 1:
            sibling_modelo, sibling_expectation = counterpart_matches[0]
            matches.append(_ReconciliationContract(expectation, sibling_modelo, sibling_expectation))

    # Ambiguous or absent registry pairing is a closed no-op.  In particular,
    # never guess a sibling model from a Python constant or an expectation id.
    return matches[0] if len(matches) == 1 else None


def _casilla_decimal(values: Mapping[CasillaId, Decimal], casilla: CasillaId) -> Decimal:
    """Read a persisted Decimal, using only the neutral arithmetic identity for absence."""
    value = values.get(casilla)
    return value if value is not None else Decimal("0")


def _sum_declared_casillas(
    values: Mapping[CasillaId, Decimal],
    casilla_ids: tuple[CasillaId, ...],
) -> Decimal:
    """Aggregate the registry-declared operand casillas with generic addition."""
    return sum((_casilla_decimal(values, casilla) for casilla in casilla_ids), Decimal("0"))


def _sibling_work_unit(
    *,
    work_unit: WorkUnit,
    sibling_modelo: str,
    catalogue: WorkUnitCatalogue,
) -> WorkUnit | None:
    """Select the active same-period counterpart through the canonical policy."""
    resolution = select_modelo_work_resolution(
        ModeloWorkSelectorRequest(
            bucket_id=work_unit.bucket_id,
            modelo=ModeloCode(sibling_modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        ),
        catalogue=catalogue,
        bucket_id=work_unit.bucket_id,
        mode=ModeloWorkSelectionMode.ACTIVE_NATURAL,
    )
    if resolution.state is ModeloWorkSelectorState.ABSENT:
        return None
    resolved_work_unit = resolution.work_unit
    if resolved_work_unit is None:
        raise ModeloValidationError("a present work-unit selection must carry the work unit it selected")
    return resolved_work_unit


_REVISION_RECONCILE_PRIORITY: Mapping[CalculationRevisionState, int] = {
    CalculationRevisionState.PRESENTADO: 4,
    CalculationRevisionState.PRESENTADO_SUPERSEDIDO: 3,
    CalculationRevisionState.VERIFICADO_COMPLETO: 2,
    CalculationRevisionState.BORRADOR: 1,
}


def _reconcile_revision_priority(revision: CalculationRevision) -> tuple[int, datetime]:
    return (_REVISION_RECONCILE_PRIORITY.get(revision.state, 0), revision.updated_at)


def _reconcile_revision_for_work_unit(
    unit: WorkUnit,
    revisions: CalculationRevisionCatalogue,
) -> CalculationRevision | None:
    """Resolve the strongest current calculation revision for a work unit."""
    for pointer in (unit.filed_calculation_revision_id, unit.current_calculation_revision_id):
        if pointer:
            revision = revisions.get(pointer)
            if revision is not None:
                from .calculation_revision_gate import require_calculation_revision_coordinates_current

                require_calculation_revision_coordinates_current(revision)
                return revision
    candidates = revisions.for_work_unit(unit.work_unit_id)
    if not candidates:
        return None
    revision = max(candidates, key=_reconcile_revision_priority)
    from .calculation_revision_gate import require_calculation_revision_coordinates_current

    require_calculation_revision_coordinates_current(revision)
    return revision


def m303_m349_intracom_reconcile_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation | None = None,
) -> list[ModeloVerificationFinding]:
    """Compare the two registry-declared cross-model operand aggregates.

    The selected expectation supplies both operand sets, tolerance, expectation
    identity, and legal/source provenance.  A counterpart work unit and its
    persisted revision are required; absent or ambiguous authority/work state
    stays a closed no-op.  A material gap produces the existing non-blocking
    reconciliation warning.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return m303_m349_intracom_reconcile_findings(
                work_unit=work_unit,
                target=target,
                work_unit_repository=work_unit_repository,
                calculation_repository=calculation_repository,
                operation=indexed_operation,
            )
    contract = _selected_reconciliation_contract(work_unit, operation=operation)
    if contract is None:
        return []

    sibling_unit = _sibling_work_unit(
        work_unit=work_unit,
        sibling_modelo=contract.sibling_modelo,
        catalogue=work_unit_repository.load(),
    )
    if sibling_unit is None:
        return []
    sibling_revision = _reconcile_revision_for_work_unit(sibling_unit, calculation_repository.load())
    if sibling_revision is None:
        return []

    own_total = _sum_declared_casillas(
        target.casilla_values,
        tuple(contract.expectation.reconcile_when_present_casilla_ids),
    )
    sibling_total = _sum_declared_casillas(
        sibling_revision.casilla_values,
        tuple(contract.sibling_expectation.reconcile_when_present_casilla_ids),
    )
    if own_total == 0 and sibling_total == 0:
        return []

    gap = abs(own_total - sibling_total)
    if gap <= Decimal(contract.expectation.tolerance):
        return []

    return [
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            severity=ModeloVerificationFindingSeverity.WARNING,
            message_locale_key="application.modelo.findings.m303_m349_intracom_reconciliation_mismatch",
            message_facts={
                "period_code": work_unit.period.registry_token,
                "filing_year": work_unit.filing_year,
                "m303_total": own_total,
                "m349_total": sibling_total,
                "gap": gap,
            },
            expectation_id=contract.expectation.id,
            legal_refs=tuple(str(ref) for ref in contract.expectation.legal_refs),
            source_refs=tuple(str(ref) for ref in contract.expectation.source_refs),
        ),
    ]


__all__ = ["m303_m349_intracom_reconcile_findings"]
