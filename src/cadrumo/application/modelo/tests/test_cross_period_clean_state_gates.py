"""Workflow-boundary tests for cross-period clean-state filing gates."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.inbound.pdf import source_pdf_reference_path
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.justificante import Justificante
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import ExternalEvidence, ExternalEvidenceKind, ModeloRecord, ModeloRecordStatus, derive_filing_record_id
from ....domain.modelos.filing_repository import upsert_filing_record
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import (
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
    cross_period_dependency_requirements,
)
from .._verification_actions import verify_modelo_revision
from .._verification_cross_period import _cross_period_clean_state_findings
from ..work_lifecycle import create_work_unit
from ..external_import_actions import import_external_filing_evidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39039039-0390-4390-8390-390390390390"
_CLOCK = datetime(2026, 6, 5, 11, 0, 0, tzinfo=UTC)
_M303_SOURCE_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_M303_SOURCE_CASILLA_01")


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
    )


def _store_ready_profile_record(*, activity_start_date: str | None = None) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=str(_workflow_profile().tax_id)),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="design"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value=IVARegime.GENERAL.value),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                *(
                    (UserProfileFact(path="censo.activity_start_date", value=activity_start_date),)
                    if activity_start_date is not None
                    else ()
                ),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
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
        period=Period.from_year_and_code(2025, "0A"),
        revision_id="2025-clean-state-test",
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("390"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        revision_id="2025-clean-state-test",
        name="390-2025-0A",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    work_unit_repository.save(upsert_work_unit(work_unit_repository.load(), work_unit))
    casilla_values: dict[CasillaId, Decimal] = {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), revision))
    return revision_id


def _source_values(period: str, source_casilla_ids: tuple[CasillaId, ...]) -> dict[CasillaId, Decimal]:
    period_ordinal = {"1T": 1, "2T": 2, "3T": 3, "4T": 4}[period]
    return {casilla_id: Decimal(period_ordinal * (index + 1)) for index, casilla_id in enumerate(source_casilla_ids)}


def _persist_justificante_metadata(csv: str, *, modelo: str, period: str, filing_year: int) -> None:
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    JustificanteRepository().save(
        Justificante(
            csv=csv,
            modelo=modelo,
            period=Period.from_year_and_code(filing_year, period),
            ejercicio=str(filing_year),
            presentation_id=None,
            presented_at=_CLOCK,
            tax_id="X1234567L",
            total_a_ingresar=None,
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
            source_pdf_path=source_pdf_reference_path(source_pdf_sha256),
            source_pdf_sha256=source_pdf_sha256,
            parsed_at=_CLOCK,
        ),
    )


def _seed_303_cross_period_sources(
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    observation_repository: CalculationObservationRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    csv_periods: set[str],
) -> None:
    snapshot = bundled_authority().snapshot("390", filing_year=2025, period="0A")
    source_casilla_ids_by_period: dict[str, set[CasillaId]] = {}
    for requirement in cross_period_dependency_requirements(snapshot):
        source_casilla_ids_by_period.setdefault(
            requirement.period.registry_token,
            set(),
        ).update(requirement.source_casilla_ids)

    for period, source_casilla_ids in sorted(source_casilla_ids_by_period.items()):
        evidence_kind = (
            ExternalEvidenceKind.AEAT_CSV_REGISTER
            if period in csv_periods
            else ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
        )
        evidence_reference_id = f"AEAT-{period}"
        source_snapshot = bundled_authority().snapshot("303", filing_year=2025, period=period)
        if evidence_kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF:
            _persist_justificante_metadata(evidence_reference_id, modelo="303", period=period, filing_year=2025)
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, period),
            revision_id=source_snapshot.revision.id,
            repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
            clock=_CLOCK,
        )
        values = _source_values(period, tuple(sorted(source_casilla_ids)))
        if evidence_kind is ExternalEvidenceKind.AEAT_CSV_REGISTER:
            _seed_source_filing_record_without_import_flow(
                work_unit=work_unit,
                casilla_values=values,
                evidence_kind=evidence_kind,
                evidence_reference_id=evidence_reference_id,
                calculation_repository=calculation_repository,
                filing_repository=filing_repository,
            )
        else:
            import_external_filing_evidence(
                work_unit_id=work_unit.work_unit_id,
                casilla_values=values,
                evidence_kind=evidence_kind,
                evidence_reference_id=evidence_reference_id,
                work_unit_repository=work_unit_repository,
                calculation_repository=calculation_repository,
                filing_repository=filing_repository,
                bucket_event_repository=bucket_event_repository,
                expected_tax_id="X1234567L",
                clock=_CLOCK,
            )
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="303",
                    filing_year=2025,
                    period=period,
                    observations=registry_grounded_observations(
                        modelo="303",
                        filing_year=2025,
                        period=period,
                        casilla_values=values,
                    ),
                ),
                source_kind="aeat_sede_justificante",
                captured_at=_CLOCK,
                stamped_revision_id=source_snapshot.revision.id,
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": f"EXP-303-2025-{period}",
                    "aeat_justificante_csv": evidence_reference_id,
                    "authenticated_identity": "X1234567L",
                },
            )
        )


def _seed_source_filing_record_without_import_flow(
    *,
    work_unit: WorkUnit,
    casilla_values: dict[CasillaId, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
) -> None:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revisions = calculation_repository.load()
    calculation_repository.save(
        upsert_calculation_revision(
            revisions,
            CalculationRevision(
                calculation_revision_id=revision_id,
                work_unit_id=work_unit.work_unit_id,
                state=CalculationRevisionState.PRESENTADO,
                casilla_values=casilla_values,
                observations=registry_grounded_observations(
                    modelo=str(work_unit.modelo),
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                    casilla_values=casilla_values,
                ),
                created_at=_CLOCK,
                updated_at=_CLOCK,
                verified_at=_CLOCK,
                verified_by="aeat-import-test",
                filed_at=_CLOCK,
                filed_by="aeat-import-test",
                filing_instance_evidence=None,
                source_provenance=(),
            ),
        ),
    )
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat-import-test",
    )
    filings = filing_repository.load()
    filing_repository.save(
        upsert_filing_record(
            filings,
            ModeloRecord(
                filing_record_id=filing_id,
                work_unit_id=work_unit.work_unit_id,
                calculation_revision_id=revision_id,
                bucket_id=work_unit.bucket_id,
                modelo=ModeloCode(str(work_unit.modelo)),
                filing_year=work_unit.filing_year,
                period=work_unit.period,
                filed_at=_CLOCK,
                filed_by="aeat-import-test",
                aeat_accepted=True,
                status=ModeloRecordStatus.VIGENTE,
                external_evidence=ExternalEvidence(
                    kind=evidence_kind,
                    reference_id=evidence_reference_id,
                    imported_at=_CLOCK,
                ),
            ),
        ),
    )


def _clean_state_repair_evidence(
    blockers: tuple[CrossPeriodCleanStateBlocker, ...],
    *,
    missing_member_nifs: tuple[str, ...] = (),
    unexpected_member_nifs: tuple[str, ...] = (),
) -> CrossPeriodDependencyEvidence:
    return CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            source_casilla_ids=(_M303_SOURCE_CASILLA_01,),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=("binding-303-casilla-01",),
            legal_refs=("ley-58-2003:art-119",),
            source_refs=("aeat-modelo-303-procedure",),
        ),
        missing_member_nifs=missing_member_nifs,
        unexpected_member_nifs=unexpected_member_nifs,
        blockers=blockers,
    )


def _clean_state_repair_verdict(
    evidence: CrossPeriodDependencyEvidence,
) -> CrossPeriodCleanStateVerdict:
    return CrossPeriodCleanStateVerdict(
        bucket_id=_BUCKET_ID,
        target_modelo="390",
        target_filing_year=2025,
        target_period=Period.from_year_and_code(2025, "0A"),
        dependencies=(evidence,),
    )


def test_cross_period_clean_state_blockers_remain_factual_without_recovery_prose() -> None:
    evidence = _clean_state_repair_evidence(
        (CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER,),
        missing_member_nifs=(),
        unexpected_member_nifs=(),
    )

    (finding,) = _cross_period_clean_state_findings(_clean_state_repair_verdict(evidence))

    assert finding.severity.value == "blocking"
    assert "missing_expected_group_member_roster" in str(finding.message_facts["blocker_codes"]).split("|")
    assert "next_action" not in finding.model_dump(mode="json")


def test_verify_modelo_390_persists_cross_period_clean_state_blockers_when_prior_filings_are_missing(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _store_ready_profile_record()
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
        finding.message_facts.get("source_modelo") == "303"
        and "missing_observation" in str(finding.message_facts["blocker_codes"]).split("|")
        for finding in cross_period_findings
    )
    assert all("next_action" not in finding.model_dump(mode="json") for finding in cross_period_findings)
    assert len(stored_reports) == 1
    assert stored_reports[0] == report


def test_verify_modelo_390_refuses_csv_register_prior_filing_without_justificante(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _store_ready_profile_record()
        objects = profile.repository
        work_units = WorkUnitCatalogueRepository(objects=objects)
        calculations = CalculationRevisionCatalogueRepository(objects=objects, bucket_id=_BUCKET_ID)
        filings = ModeloRecordCatalogueRepository(objects=objects, bucket_id=_BUCKET_ID)
        reports = VerificationReportCatalogueRepository(objects=objects, bucket_id=_BUCKET_ID)
        observations = CalculationObservationRepository(objects=objects)
        events = BucketEventHistoryRepository(objects=objects)
        _seed_303_cross_period_sources(
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
            observation_repository=observations,
            bucket_event_repository=events,
            csv_periods={"1T"},
        )
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

    cross_period_findings = tuple(
        finding for finding in report.findings if finding.kind.value == "cross_period_dependency_unclean"
    )
    assert report.granted_verificado_completo is False
    assert any(
        finding.message_facts.get("source_period") == "1T"
        and "missing_external_evidence_record" in str(finding.message_facts["blocker_codes"]).split("|")
        for finding in cross_period_findings
    )


def test_verify_fails_closed_when_profile_records_no_activity_start_date(tmp_path: Path) -> None:
    """With no activity-start date and missing priors, the gate fails closed.

    A profile that records no ``activity_start_date`` cannot decide whether a
    missing prior filing is pre-activity (no obligation) or a genuinely missing
    filing. When an evidence-missing cross-period dependency blocks, the gate
    surfaces a BLOCKING finding prompting the operator to record the date, rather
    than silently opening. The grant stays refused.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _store_ready_profile_record()
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
        no_activity_profile = _workflow_profile()
        assert no_activity_profile.activity_start_date is None

        report = verify_modelo_revision(
            revision_id,
            actor="test-operator",
            workflow_profile=no_activity_profile,
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
            verification_repository=reports,
            calculation_observation_repository=observations,
            bucket_event_repository=events,
            clock=_CLOCK,
        )

    assert report.granted_verificado_completo is False
    fail_closed_findings = tuple(
        finding
        for finding in report.findings
        if finding.kind.value == "cross_period_dependency_unclean"
        and finding.message_locale_key == "application.modelo.findings.cross_period_activity_start_missing"
    )
    assert fail_closed_findings
    finding = fail_closed_findings[0]
    assert finding.severity.value == "blocking"
    assert "next_action" not in finding.model_dump(mode="json")
