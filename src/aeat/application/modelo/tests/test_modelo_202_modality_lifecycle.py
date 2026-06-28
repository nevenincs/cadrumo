"""Modelo 202 incomplete-modality revisions cannot become filing-grade.

These tests exercise the real work-unit, calculation, verification, prior-filing
observation, and profile paths. An S.L. without the prior-12-month INCN may still
calculate, but verification must keep the revision in BORRADOR until the INCN
fact determines the Modelo 202 modality.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import Modelo202Modality, RegistryModeloObservation, derive_modelo_202_modality
from ....domain.deadlines import EntityType, IVARegime, LegalEntityForm, TaxpayerProfile
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ExternalEvidenceKind,
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
)
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....domain.modelos._work_unit import WorkUnit
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    CalculationRevisionStateError,
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    import_external_filing_evidence,
    verify_modelo_revision,
)
from .._selectors import ModeloCalculationRevisionSelectorStateError, select_exportable_revision
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
_BUCKET_ID = "m202-modality-lifecycle"
_TAX_ID = "B12345674"
_M202_RELATION_BINDING = "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
_M200_CUOTA_LIQUIDA = "DP200014B:00592"


def _workflow_profile(incn: Decimal | None) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        activity_start_date=date(2020, 1, 1),
        incn_prior_12_months=incn,
        new_entity_first_two_profit_periods=False,
    )


def _seed_profile(*, bucket_id: str, incn: Decimal | None) -> None:
    facts = [
        UserProfileFact(path="identity.tax_id", value=_TAX_ID),
        UserProfileFact(path="identity.name", value="Marta"),
        UserProfileFact(path="identity.surnames", value="Sociedad Limitada"),
        UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
        UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
        UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
        UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
        UserProfileFact(path="filing_export.declaration_type", value="1"),
    ]
    if incn is not None:
        facts.append(UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=incn))
    UserProfileLifecycleRepository(bucket_id=bucket_id).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Test runtime profile",
            facts=tuple(facts),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def _seed_prior_m200_evidence(*, bucket_id: str) -> None:
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    snapshot = resources().modelos.authority.snapshot("200", filing_year=2024, period="0A")
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="200",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_CLOCK,
    )
    evidence_reference_id = "JUST-M200-2024-0A"
    casilla_values = {_M200_CUOTA_LIQUIDA: Decimal("0")}
    persist_justificante_metadata(
        evidence_reference_id,
        modelo="200",
        filing_year=2024,
        period="0A",
        captured_at=_CLOCK,
        tax_id=_TAX_ID,
    )
    import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor="aeat-import-test",
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        expected_tax_id=_TAX_ID,
        clock=_CLOCK,
    )
    CalculationObservationRepository().save_observation(
        RegistryModeloObservation(
            modelo="200",
            filing_year=2024,
            period="0A",
            observations=registry_grounded_observations(
                modelo="200",
                filing_year=2024,
                period="0A",
                casilla_values=casilla_values,
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_CLOCK,
        stamped_revision_id=snapshot.revision.id,
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "EXP-M200-2024-0A",
            "aeat_justificante_csv": evidence_reference_id,
            "authenticated_identity": _TAX_ID,
        },
    )


def _calculate_m202(
    *,
    bucket_id: str,
) -> tuple[
    WorkUnit,
    CalculationRevision,
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
]:
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    verification_repo = VerificationReportCatalogueRepository()
    snapshot = resources().modelos.authority.snapshot("202", filing_year=2026, period="1P")
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="202",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1P"),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_CLOCK,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-test",
        casilla_inputs={},
        binding_values={_M202_RELATION_BINDING: Decimal("0")},
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        clock=_CLOCK,
    )
    refreshed_work_unit = work_repo.load().get(work_unit.work_unit_id)
    assert refreshed_work_unit is not None
    return refreshed_work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo


def test_m202_incomplete_modality_calculates_but_cannot_verify_file_or_export(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=None)
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID)
        work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo = _calculate_m202(
            bucket_id=_BUCKET_ID,
        )
        workflow_profile = _workflow_profile(None)

        assert derive_modelo_202_modality(workflow_profile).modality is Modelo202Modality.INCOMPLETE
        assert revision.state is CalculationRevisionState.BORRADOR

        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-test",
            workflow_profile=workflow_profile,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            verification_repository=verification_repo,
            clock=_CLOCK,
        )

        assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
        assert report.granted_verificado_completo is False
        modality_finding = next(
            finding
            for finding in report.findings
            if finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
            and "taxpayer_type.incn_prior_12_months" in finding.message
        )
        assert modality_finding.severity.value == "blocking"
        assert "INCN prior 12 months" in modality_finding.message
        stored = calc_repo.load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored.state is CalculationRevisionState.BORRADOR

        with pytest.raises(CalculationRevisionStateError, match="VERIFICADO_COMPLETO"):
            file_modelo_revision(
                revision.calculation_revision_id,
                actor="operator-test",
                workflow_profile=workflow_profile,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
            )
        with pytest.raises(ModeloCalculationRevisionSelectorStateError, match="still draft"):
            select_exportable_revision(work_unit, calculation_repository=calc_repo)


@pytest.mark.parametrize("incn", (Decimal("500000"), Decimal("7000000")))
def test_m202_declared_incn_below_or_above_threshold_can_verify(tmp_path: Path, incn: Decimal) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=incn)
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID)
        _work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo = _calculate_m202(
            bucket_id=_BUCKET_ID,
        )

        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-test",
            workflow_profile=_workflow_profile(incn),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            verification_repository=verification_repo,
            clock=_CLOCK,
        )

        assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
        assert report.granted_verificado_completo is True
        stored = calc_repo.load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored.state is CalculationRevisionState.VERIFICADO_COMPLETO
