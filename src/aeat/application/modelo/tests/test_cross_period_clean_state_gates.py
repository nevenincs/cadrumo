"""Workflow-boundary tests for cross-period clean-state filing gates."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....core import Period
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.justificante import Justificante, JustificanteRepository
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogueRepository,
    CalculationRevisionState,
    ExternalEvidenceKind,
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
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
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
from .. import create_work_unit, import_external_filing_evidence, verify_modelo_revision
from .._actions import _cross_period_clean_state_next_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "cross-period-clean-state-gates"
_CLOCK = datetime(2026, 6, 5, 11, 0, 0, tzinfo=UTC)
_M303_REVISION = "2023-y-siguientes"


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


def _source_values(period: str, source_casillas: tuple[str, ...]) -> dict[str, Decimal]:
    period_ordinal = {"1T": 1, "2T": 2, "3T": 3, "4T": 4}[period]
    return {casilla_id: Decimal(period_ordinal * (index + 1)) for index, casilla_id in enumerate(source_casillas)}


def _persist_justificante_metadata(csv: str, *, modelo: str, period: str, filing_year: int) -> None:
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    JustificanteRepository().save(
        Justificante(
            csv=csv,
            modelo=modelo,
            period=period,
            ejercicio=str(filing_year),
            presentation_id=None,
            presented_at=_CLOCK,
            tax_id="X1234567L",
            total_a_ingresar=None,
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
            source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
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
    snapshot = resources().modelos.authority.snapshot("390", filing_year=2025, period="0A")
    source_casillas_by_period: dict[str, set[str]] = {}
    for requirement in cross_period_dependency_requirements(snapshot):
        source_casillas_by_period.setdefault(requirement.period, set()).update(requirement.source_casillas)

    for period, source_casillas in sorted(source_casillas_by_period.items()):
        evidence_kind = (
            ExternalEvidenceKind.AEAT_CSV_REGISTER
            if period in csv_periods
            else ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
        )
        evidence_reference_id = f"AEAT-{period}"
        if evidence_kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF:
            _persist_justificante_metadata(evidence_reference_id, modelo="303", period=period, filing_year=2025)
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, period),
            revision_id=_M303_REVISION,
            repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
            clock=_CLOCK,
        )
        values = _source_values(period, tuple(sorted(source_casillas)))
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
        observation_repository.save_observation(
            RegistryModeloObservation(
                modelo="303",
                filing_year=2025,
                period=period,
                observations=tuple(
                    CasillaObservation(casilla_id=casilla_id, value=value) for casilla_id, value in values.items()
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_CLOCK,
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
            period="1T",
            source_casillas=("01",),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=("binding-303-casilla-01",),
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
        target_period="0A",
        dependencies=(evidence,),
    )


@pytest.mark.parametrize(
    ("blockers", "expected_fragments", "missing_member_nifs", "unexpected_member_nifs"),
    (
        (
            (CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER,),
            (
                "Configure the expected grupo member roster",
                "aeat app live filed pull-sources --modelo 390 --year 2025 --period 0A",
            ),
            (),
            (),
        ),
        (
            (CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE,),
            (
                "Capture every expected grupo member filing",
                "Missing members: B00000001",
            ),
            ("B00000001",),
            (),
        ),
        (
            (CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE,),
            (
                "Review the grupo roster",
                "unexpected captured members: C00000002",
            ),
            (),
            ("C00000002",),
        ),
        (
            (CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE,),
            ("aeat app registry verify-filed-state --observation PATH",),
            (),
            (),
        ),
        (
            (CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE,),
            ("Use AEAT evidence for upstream values",),
            (),
            (),
        ),
        (
            (CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION,),
            ("aeat app modelo reconcile file WORK_UNIT_ID --file PATH",),
            (),
            (),
        ),
        (
            (CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD,),
            ("aeat app modelo reconcile file WORK_UNIT_ID --file PATH",),
            (),
            (),
        ),
        (
            (CrossPeriodCleanStateBlocker.MISSING_CALCULATION_REVISION,),
            ("Recalculate and verify the upstream work unit",),
            (),
            (),
        ),
    ),
)
def test_cross_period_clean_state_repair_diagnostics_map_blockers_to_operator_actions(
    blockers: tuple[CrossPeriodCleanStateBlocker, ...],
    expected_fragments: tuple[str, ...],
    missing_member_nifs: tuple[str, ...],
    unexpected_member_nifs: tuple[str, ...],
) -> None:
    evidence = _clean_state_repair_evidence(
        blockers,
        missing_member_nifs=missing_member_nifs,
        unexpected_member_nifs=unexpected_member_nifs,
    )

    next_action = _cross_period_clean_state_next_action(
        _clean_state_repair_verdict(evidence),
        evidence,
    )

    assert all(fragment in next_action for fragment in expected_fragments)


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
    assert any(
        finding.next_action is not None
        and "aeat app live filed pull-sources --modelo 390 --year 2025 --period 0A" in finding.next_action
        and "aeat app modelo reconcile file WORK_UNIT_ID --file PATH" in finding.next_action
        for finding in cross_period_findings
    )
    assert len(stored_reports) == 1
    assert stored_reports[0] == report


def test_verify_modelo_390_refuses_csv_register_prior_filing_without_justificante(
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
        "period=1T" in finding.message and "blockers=missing_justificante_verification" in finding.message
        for finding in cross_period_findings
    )
