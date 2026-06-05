"""Real-behavior coverage for cross-period clean-state dependency proof."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos import (
    CalculationRevisionCatalogueRepository,
    CalculationRevisionState,
    ExternalEvidenceKind,
    ModeloRecordCatalogueRepository,
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
    VerificationReportCatalogueRepository,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo import (
    calculate_modelo_revision,
    create_work_unit,
    import_external_filing_evidence,
    verify_modelo_revision,
)
from .. import (
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyOrigin,
    cross_period_dependency_requirements,
    evaluate_cross_period_clean_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "default"
_M390_YEAR = 2025
_M390_PERIOD = "0A"
_M390_REVISION = "2010-y-siguientes"
_M303_REVISION = "2023-y-siguientes"
_CLOCK = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _snapshot_390():
    return resources().modelos.authority.snapshot("390", filing_year=_M390_YEAR, period=_M390_PERIOD)


def _source_values(period: str, source_casillas: tuple[str, ...]) -> dict[str, Decimal]:
    period_ordinal = {"1T": 1, "2T": 2, "3T": 3, "4T": 4}[period]
    return {
        casilla_id: Decimal(period_ordinal * (index + 1))
        for index, casilla_id in enumerate(source_casillas)
    }


def _save_source_observation(
    repository: CalculationObservationRepository,
    *,
    period: str,
    source_values: dict[str, Decimal],
) -> None:
    repository.save_observation(
        RegistryModeloObservation(
            modelo="303",
            filing_year=_M390_YEAR,
            period=period,
            observations=tuple(
                CasillaObservation(casilla_id=casilla_id, value=value)
                for casilla_id, value in source_values.items()
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_CLOCK,
    )


def _seed_official_303_source_filings(
    *,
    observation_repository: CalculationObservationRepository,
) -> None:
    source_casillas_by_period: dict[str, set[str]] = {}
    for requirement in cross_period_dependency_requirements(_snapshot_390()):
        source_casillas_by_period.setdefault(requirement.period, set()).update(requirement.source_casillas)

    for period, source_casillas in sorted(source_casillas_by_period.items()):
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_M390_YEAR,
            period=period,
            revision_id=_M303_REVISION,
            clock=_CLOCK,
        )
        values = _source_values(period, tuple(sorted(source_casillas)))
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values=values,
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id=f"JUST-{period}",
            actor="aeat-import-test",
            clock=_CLOCK,
        )
        _save_source_observation(
            observation_repository,
            period=period,
            source_values=values,
        )


def test_cross_period_clean_state_blocks_missing_required_prior_filings(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISSING_OBSERVATION in verdict.blockers
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in verdict.blockers


def test_cross_period_requirements_include_relation_rollups(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snapshot = resources().modelos.authority.snapshot("180", filing_year=2026, period="0A")

    requirements = cross_period_dependency_requirements(snapshot)

    assert any(
        requirement.origin is CrossPeriodDependencyOrigin.REGISTRY_RELATION
        and requirement.source_modelo == "115"
        and requirement.period == "1T"
        for requirement in requirements
    )


def test_cross_period_clean_state_accepts_aeat_attested_reconciled_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(observation_repository=observation_repository)

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is True
    assert verdict.blockers == ()


def test_verify_modelo_revision_refuses_m390_when_prior_filings_are_not_clean(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="390",
            filing_year=_M390_YEAR,
            period=_M390_PERIOD,
            revision_id=_M390_REVISION,
            clock=_CLOCK,
        )
        snapshot = _snapshot_390()
        binding_values = {binding.id: Decimal("0") for binding in snapshot.revision.bindings}
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={},
            binding_values=binding_values,
            calculation_repository=CalculationRevisionCatalogueRepository(),
            bucket_event_repository=BucketEventHistoryRepository(),
            clock=_CLOCK,
        )

        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-test",
            workflow_profile=_workflow_profile(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            bucket_event_repository=BucketEventHistoryRepository(),
            calculation_observation_repository=CalculationObservationRepository(),
            clock=_CLOCK,
        )
        reloaded = CalculationRevisionCatalogueRepository().load().get(revision.calculation_revision_id)

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
    assert reloaded is not None
    assert reloaded.state is CalculationRevisionState.BORRADOR
    assert any(
        finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        for finding in report.findings
    )
