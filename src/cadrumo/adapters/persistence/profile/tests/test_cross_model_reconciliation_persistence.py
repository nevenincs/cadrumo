"""Cross-model comparisons consume real encrypted same-profile catalogues."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from .....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from .....application.modelo.verification_model_findings import append_model_specific_findings
from .....core.casilla_id import validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.verification_report import ModeloVerificationFindingKind
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from ..iva_compensation_history import IvaCompensationHistoryRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("case", ["match", "drift", "missing"])
def test_cross_model_reconciliation_from_encrypted_catalogues(tmp_path, case):
    operation = published_authority_operation()
    bucket_id = "00000000-0000-4000-8000-000000000349"
    period = Period.from_year_and_code(2025, "1T")
    clock = datetime(2026, 10, 4, tzinfo=UTC)
    units = []
    calculations = []
    for modelo in ("303", "349"):
        snapshot = operation.snapshot(modelo, filing_year=2025, period="1T")
        unit_id = derive_work_unit_id(
            bucket_id=bucket_id, modelo=modelo, filing_year=2025, period=period, revision_id=snapshot.revision.id
        )
        unit = WorkUnit(
            work_unit_id=unit_id,
            bucket_id=bucket_id,
            modelo=ModeloCode(modelo),
            filing_year=2025,
            period=period,
            revision_id=snapshot.revision.id,
            name=f"{modelo}-2025-1T",
            created_at=clock,
            updated_at=clock,
        )
        values = {
            validated_casilla_id(key, surface="test"): Decimal(value)
            for key, value in (
                {"10": "6000", "59": "4000"}
                if modelo == "303"
                else {"decl.importe-operaciones": "8000" if case == "drift" else "10000"}
            ).items()
        }
        if case == "missing" and modelo == "349":
            values.clear()
        evidence = (
            general_m303_filing_evidence(period, reference="test:cross-model-encrypted", operation=operation)
            if modelo == "303"
            else None
        )
        revision_id = derive_calculation_revision_id(
            work_unit_id=unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=values,
            filing_instance_evidence=evidence,
            source_provenance=(),
        )
        calculation = CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=unit_id,
            registry_snapshot_ref=RegistrySnapshotRef(
                modelo=modelo, modelo_year=2025, period="1T", revision_id=snapshot.revision.id
            ),
            state=CalculationRevisionState.BORRADOR,
            casilla_values=values,
            observations=registry_grounded_observations(
                modelo=modelo, filing_year=2025, period="1T", casilla_values=values
            ),
            filing_instance_evidence=evidence,
            source_provenance=(),
            created_at=clock,
            updated_at=clock,
        )
        units.append(unit.model_copy(update={"current_calculation_revision_id": revision_id}))
        calculations.append(calculation)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        unit_repository = WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(bucket_id=bucket_id, objects=profile.repository)
        unit_repository.save(WorkUnitCatalogue(work_units={unit.work_unit_id: unit for unit in units}))
        calculation_repository.save(
            CalculationRevisionCatalogue(
                revisions={revision.calculation_revision_id: revision for revision in calculations}
            )
        )
        target = calculation_repository.load(operation=operation).get(calculations[0].calculation_revision_id)
        assert target is not None
        findings = []
        append_model_specific_findings(
            findings,
            failures_by_finding_id={},
            work_unit=units[0],
            target=target,
            work_unit_repository=unit_repository,
            calculation_repository=calculation_repository,
            observation_repository=CalculationObservationRepository(objects=profile.repository),
            iva_history_repository=IvaCompensationHistoryRepository(objects=profile.repository),
            operation=operation,
        )
    if case == "match":
        assert findings == []
    else:
        assert len(findings) == 1
        assert findings[0].kind is (
            ModeloVerificationFindingKind.ADVISORY
            if case == "missing"
            else ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
        )
