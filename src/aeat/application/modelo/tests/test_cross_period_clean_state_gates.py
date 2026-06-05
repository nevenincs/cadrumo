"""Workflow-boundary tests for cross-period clean-state filing gates."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.buckets import BucketEventHistoryRepository
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogueRepository,
    CalculationRevisionState,
    ModeloCode,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    WorkUnit,
    WorkUnitCatalogueRepository,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from .. import verify_modelo_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "cross-period-clean-state-gates"
_CLOCK = datetime(2026, 6, 5, 11, 0, 0, tzinfo=UTC)


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
    )


def _persist_390_draft(
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
) -> str:
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=2025,
        period="0A",
        revision_id="2025-clean-state-test",
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("390"),
        filing_year=2025,
        period="0A",
        revision_id="2025-clean-state-test",
        name="390-2025-0A",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    work_unit_repository.save(upsert_work_unit(work_unit_repository.load(), work_unit))
    casilla_values: dict[str, Decimal] = {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), revision))
    return revision_id


def test_verify_modelo_390_persists_cross_period_clean_state_blockers_when_prior_filings_are_missing(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        work_units = WorkUnitCatalogueRepository(objects=objects)
        calculations = CalculationRevisionCatalogueRepository(objects=objects, bucket_id=_BUCKET_ID)
        filings = ModeloRecordCatalogueRepository(objects=objects, bucket_id=_BUCKET_ID)
        reports = VerificationReportCatalogueRepository(objects=objects, bucket_id=_BUCKET_ID)
        observations = CalculationObservationRepository(objects=objects)
        events = BucketEventHistoryRepository(objects=objects)
        revision_id = _persist_390_draft(
            work_unit_repository=work_units,
            calculation_repository=calculations,
        )

        report = verify_modelo_revision(
            revision_id,
            actor="test-operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
            verification_repository=reports,
            calculation_observation_repository=observations,
            bucket_event_repository=events,
            clock=_CLOCK,
        )
        stored_reports = reports.load().for_calculation_revision(revision_id)

    cross_period_findings = tuple(
        finding for finding in report.findings if finding.kind.value == "cross_period_dependency_unclean"
    )
    assert report.granted_verificado_completo is False
    assert cross_period_findings
    assert any(
        "modelo=303" in finding.message and "blockers=missing_observation" in finding.message
        for finding in cross_period_findings
    )
    assert len(stored_reports) == 1
    assert stored_reports[0] == report
