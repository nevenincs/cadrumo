"""Real-behavior coverage for cross-period clean-state dependency proof."""

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
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepository,
    CalculationRevisionState,
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloCode,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepository,
    ModeloRecordStatus,
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
    VerificationReportCatalogueRepository,
    derive_calculation_revision_id,
    derive_filing_record_id,
)
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
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
    CrossPeriodExpectedMemberSet,
    cross_period_dependency_inventory,
    cross_period_dependency_requirements,
    evaluate_cross_period_clean_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "default"
_M390_YEAR = 2025
_M390_PERIOD = "0A"
_M390_REVISION = "2010-y-siguientes"
_M303_REVISION = "2023-y-siguientes"
_M353_YEAR = 2026
_M353_PERIOD = "12"
_CLOCK = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_GROUP_MEMBER_A = "A00000000"
_GROUP_MEMBER_B = "B00000001"
_GROUP_MEMBER_C = "C00000002"


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
    return {casilla_id: Decimal(period_ordinal * (index + 1)) for index, casilla_id in enumerate(source_casillas)}


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
                CasillaObservation(casilla_id=casilla_id, value=value) for casilla_id, value in source_values.items()
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_CLOCK,
    )


def _snapshot_353():
    return resources().modelos.authority.snapshot("353", filing_year=_M353_YEAR, period=_M353_PERIOD)


def _member_fan_in_requirement():
    return next(
        requirement
        for requirement in cross_period_dependency_requirements(_snapshot_353())
        if requirement.requires_member_fan_in
    )


def _member_source_values(member_nif: str, source_casillas: tuple[str, ...]) -> dict[str, Decimal]:
    member_ordinal = {
        _GROUP_MEMBER_A: Decimal("1"),
        _GROUP_MEMBER_B: Decimal("10"),
        _GROUP_MEMBER_C: Decimal("100"),
    }[member_nif]
    return {casilla_id: member_ordinal * Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}


def _save_member_322_observation(
    repository: CalculationObservationRepository,
    *,
    member_nif: str,
    source_casillas: tuple[str, ...],
) -> None:
    repository.save_observation(
        RegistryModeloObservation(
            modelo="322",
            filing_year=_M353_YEAR,
            period=_M353_PERIOD,
            observations=tuple(
                CasillaObservation(casilla_id=casilla_id, value=value)
                for casilla_id, value in _member_source_values(member_nif, source_casillas).items()
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_CLOCK,
        member_nif=member_nif,
    )


def _seed_member_322_filing(
    observation_repository: CalculationObservationRepository,
    *,
    member_nif: str,
    source_casillas: tuple[str, ...],
    justificante_tax_id: str | None = None,
) -> None:
    values = _member_source_values(member_nif, source_casillas)
    work_unit_id = hashlib.sha256(f"322:{_M353_YEAR}:{_M353_PERIOD}:{member_nif}".encode()).hexdigest()
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values=values,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=values,
        observations=tuple(
            CasillaObservation(casilla_id=casilla_id, value=value) for casilla_id, value in values.items()
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="aeat-import-test",
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
    )
    calculation_repository = CalculationRevisionCatalogueRepository()
    calculation_catalogue = calculation_repository.load()
    calculation_repository.save(
        CalculationRevisionCatalogue(revisions={**dict(calculation_catalogue.revisions), revision_id: revision}),
    )

    evidence_reference_id = f"JUST-322-{member_nif}"
    _persist_justificante_metadata(
        evidence_reference_id,
        modelo="322",
        period=_M353_PERIOD,
        filing_year=_M353_YEAR,
        tax_id=justificante_tax_id or member_nif,
    )
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
        member_nif=member_nif,
    )
    filing_repository = ModeloRecordCatalogueRepository()
    filing_catalogue = filing_repository.load()
    filing_repository.save(
        ModeloRecordCatalogue(
            records={
                **dict(filing_catalogue.records),
                filing_id: ModeloRecord(
                    filing_record_id=filing_id,
                    work_unit_id=work_unit_id,
                    calculation_revision_id=revision_id,
                    bucket_id=_BUCKET_ID,
                    modelo=ModeloCode("322"),
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nif=member_nif,
                    filed_at=_CLOCK,
                    filed_by="aeat-import-test",
                    aeat_accepted=True,
                    external_evidence=ExternalEvidence(
                        kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                        reference_id=evidence_reference_id,
                        imported_at=_CLOCK,
                    ),
                ),
            },
        ),
    )
    _save_member_322_observation(
        observation_repository,
        member_nif=member_nif,
        source_casillas=source_casillas,
    )


def _persist_justificante_metadata(
    csv: str,
    *,
    modelo: str,
    period: str,
    filing_year: int,
    tax_id: str = "X1234567L",
) -> None:
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    JustificanteRepository().save(
        Justificante(
            csv=csv,
            modelo=modelo,
            period=period,
            ejercicio=str(filing_year),
            presentation_id=None,
            presented_at=_CLOCK,
            tax_id=tax_id,
            total_a_ingresar=None,
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
            source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            parsed_at=_CLOCK,
        ),
    )


def _live_capture_filing(*, csv: str, kind: ExternalEvidenceKind) -> ModeloRecord:
    work_unit_id = hashlib.sha256(f"130:2026:1T:{csv}".encode()).hexdigest()
    revision_id = hashlib.sha256(f"rev:{csv}".encode()).hexdigest()
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_CLOCK,
        filed_by="aeat-live-capture-test",
    )
    return ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=_CLOCK,
        filed_by="aeat-live-capture-test",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(kind=kind, reference_id=csv, imported_at=_CLOCK),
    )


def test_live_capture_evidence_clears_justificante_verification(tmp_path: Path) -> None:
    """A filing stamped with AEAT_LIVE_CAPTURE evidence clears the justificante gate."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130ABCD01"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "app_filing",
            JustificanteRepository(),
            "X1234567L",
        )

        assert CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION not in blockers
        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD not in blockers
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_csv_register_evidence_still_requires_justificante_verification(tmp_path: Path) -> None:
    """A non-justificante evidence kind (CSV register) still trips the justificante gate."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        filing = _live_capture_filing(csv="CSVREG130ABCD01", kind=ExternalEvidenceKind.AEAT_CSV_REGISTER)

        blockers = _filing_external_evidence_blockers(
            filing,
            "aeat_csv_register",
            JustificanteRepository(),
            "X1234567L",
        )

        assert CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION in blockers


def _seed_official_303_source_filings(
    *,
    observation_repository: CalculationObservationRepository,
    evidence_kind_by_period: dict[str, ExternalEvidenceKind] | None = None,
    skip_justificante_metadata_periods: set[str] | None = None,
) -> None:
    evidence_kind_by_period = evidence_kind_by_period or {}
    skip_justificante_metadata_periods = skip_justificante_metadata_periods or set()
    source_casillas_by_period: dict[str, set[str]] = {}
    for requirement in cross_period_dependency_requirements(_snapshot_390()):
        source_casillas_by_period.setdefault(requirement.period, set()).update(requirement.source_casillas)

    for period, source_casillas in sorted(source_casillas_by_period.items()):
        evidence_kind = evidence_kind_by_period.get(period, ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF)
        evidence_reference_id = f"JUST-{period}"
        if evidence_kind in {
            ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
        } and period not in skip_justificante_metadata_periods:
            _persist_justificante_metadata(evidence_reference_id, modelo="303", period=period, filing_year=_M390_YEAR)
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_M390_YEAR,
            period=Period.from_year_and_code(_M390_YEAR, period),
            revision_id=_M303_REVISION,
            clock=_CLOCK,
        )
        values = _source_values(period, tuple(sorted(source_casillas)))
        if evidence_kind in {
            ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
        } and period in skip_justificante_metadata_periods:
            _seed_legacy_source_filing_record(
                work_unit=work_unit,
                casilla_values=values,
                evidence_kind=evidence_kind,
                evidence_reference_id=evidence_reference_id,
            )
        else:
            import_external_filing_evidence(
                work_unit_id=work_unit.work_unit_id,
                casilla_values=values,
                evidence_kind=evidence_kind,
                evidence_reference_id=evidence_reference_id,
                actor="aeat-import-test",
                expected_tax_id="X1234567L",
                clock=_CLOCK,
            )
        _save_source_observation(
            observation_repository,
            period=period,
            source_values=values,
        )


def _seed_legacy_source_filing_record(
    *,
    work_unit: object,
    casilla_values: dict[str, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
) -> None:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=casilla_values,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="aeat-import-test",
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
    )
    calculation_repository = CalculationRevisionCatalogueRepository()
    calculation_catalogue = calculation_repository.load()
    calculation_repository.save(
        CalculationRevisionCatalogue(revisions={**dict(calculation_catalogue.revisions), revision_id: revision}),
    )

    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
    )
    filing_repository = ModeloRecordCatalogueRepository()
    filing_catalogue = filing_repository.load()
    filing_repository.save(
        ModeloRecordCatalogue(
            records={
                **dict(filing_catalogue.records),
                filing_id: ModeloRecord(
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
            },
        ),
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


def test_cross_period_dependency_inventory_covers_declared_2026_target_modelos(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventory = cross_period_dependency_inventory(
            resources().modelos.authority,
            filing_year=2026,
        )

    assert inventory.target_modelos == (
        "130",
        "131",
        "180",
        "190",
        "193",
        "200",
        "202",
        "303",
        "353",
        "390",
    )
    assert all(item.dependencies for item in inventory.items)
    assert any(
        item.target_modelo == "390" and item.target_period == "0A" and item.source_modelos == ("303",)
        for item in inventory.items
    )
    assert any(
        item.target_modelo == "353" and item.target_period == "12" and item.source_modelos == ("322",)
        for item in inventory.items
    )


def test_cross_period_dependency_inventory_covers_renta_2025_target_modelo(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventory = cross_period_dependency_inventory(
            resources().modelos.authority,
            filing_year=2025,
            modelos=("100",),
        )

    assert inventory.target_modelos == ("100",)
    assert len(inventory.items) == 1
    assert inventory.items[0].target_period == "0A"
    assert set(inventory.items[0].source_modelos) >= {
        "111",
        "115",
        "123",
        "130",
        "131",
        "180",
        "184",
        "190",
        "193",
    }


def test_cross_period_dependency_inventory_documents_patrimonio_foreign_asset_scope(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventories = tuple(
            cross_period_dependency_inventory(
                resources().modelos.authority,
                filing_year=filing_year,
            )
            for filing_year in (2025, 2026)
        )

    assert all("714" not in inventory.target_modelos for inventory in inventories)
    assert all("720" not in inventory.target_modelos for inventory in inventories)
    assert all("721" not in inventory.target_modelos for inventory in inventories)
    assert all("714" not in inventory.source_modelos for inventory in inventories)
    assert all("720" not in inventory.source_modelos for inventory in inventories)
    assert all("721" not in inventory.source_modelos for inventory in inventories)


def test_cross_period_clean_state_blocks_missing_group_member_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snapshot = _snapshot_353()

        verdict = evaluate_cross_period_clean_state(
            snapshot,
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    assert verdict.requires_clean_state is True
    assert any(evidence.requirement.requires_member_fan_in for evidence in verdict.dependencies)
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER in verdict.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in verdict.blockers


def test_cross_period_clean_state_blocks_group_member_fan_in_without_expected_roster(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _save_member_322_observation(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            source_casillas=requirement.source_casillas,
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A,)
    assert member_evidence.expected_member_nifs == ()
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER in member_evidence.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in member_evidence.blockers


def test_cross_period_clean_state_blocks_incomplete_expected_group_member_fan_in(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _save_member_322_observation(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            source_casillas=requirement.source_casillas,
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=_M353_PERIOD,
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A,)
    assert member_evidence.expected_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B)
    assert member_evidence.missing_member_nifs == (_GROUP_MEMBER_B,)
    assert member_evidence.unexpected_member_nifs == ()
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER not in member_evidence.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in member_evidence.blockers


def test_cross_period_clean_state_blocks_unexpected_group_member_fan_in(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        for member_nif in (_GROUP_MEMBER_A, _GROUP_MEMBER_B, _GROUP_MEMBER_C):
            _save_member_322_observation(
                observation_repository,
                member_nif=member_nif,
                source_casillas=requirement.source_casillas,
            )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=_M353_PERIOD,
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B, _GROUP_MEMBER_C)
    assert member_evidence.expected_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B)
    assert member_evidence.missing_member_nifs == ()
    assert member_evidence.unexpected_member_nifs == (_GROUP_MEMBER_C,)
    assert CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE in member_evidence.blockers


def test_cross_period_clean_state_accepts_member_scoped_group_filing_records(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        for member_nif in (_GROUP_MEMBER_A, _GROUP_MEMBER_B):
            _seed_member_322_filing(
                observation_repository,
                member_nif=member_nif,
                source_casillas=requirement.source_casillas,
            )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=_M353_PERIOD,
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert verdict.requires_clean_state is True
    assert verdict.clean is True
    assert member_evidence.clean is True
    assert member_evidence.member_filing_record_ids
    assert len(member_evidence.member_filing_record_ids) == 2
    assert member_evidence.member_calculation_revision_ids
    assert len(member_evidence.member_calculation_revision_ids) == 2


def test_cross_period_clean_state_blocks_member_filing_with_wrong_tax_id_justificante(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _seed_member_322_filing(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            justificante_tax_id=_GROUP_MEMBER_B,
            source_casillas=requirement.source_casillas,
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=_M353_PERIOD,
                    member_nifs=(_GROUP_MEMBER_A,),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in member_evidence.blockers


def test_cross_period_clean_state_blocks_taxpayer_filing_with_wrong_tax_id_justificante(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            skip_justificante_metadata_periods={"1T"},
        )
        _persist_justificante_metadata(
            "JUST-1T",
            modelo="303",
            period="1T",
            filing_year=_M390_YEAR,
            tax_id="B12345678",
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    first_quarter = next(evidence for evidence in verdict.dependencies if evidence.requirement.period == "1T")
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_superseded_upstream_filing(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(observation_repository=observation_repository)
        filing_repository = ModeloRecordCatalogueRepository()
        catalogue = filing_repository.load()
        source_record = catalogue.current_for(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_M390_YEAR,
            period=Period.from_year_and_code(_M390_YEAR, "1T"),
        )
        assert source_record is not None
        superseded_record = source_record.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": _CLOCK,
                "superseded_by_filing_record_id": "f" * 64,
            },
        )
        filing_repository.save(
            ModeloRecordCatalogue(
                records={
                    **dict(catalogue.records),
                    source_record.filing_record_id: superseded_record,
                },
            ),
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=filing_repository,
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY in verdict.blockers
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in verdict.blockers


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


def test_cross_period_clean_state_blocks_dangling_justificante_evidence_reference(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            skip_justificante_metadata_periods={"1T"},
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    first_quarter = next(evidence for evidence in verdict.dependencies if evidence.requirement.period == "1T")
    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert first_quarter.external_evidence_kind == "aeat_justificante_pdf"
    assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_csv_register_without_justificante_verification(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            evidence_kind_by_period={"1T": ExternalEvidenceKind.AEAT_CSV_REGISTER},
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    first_quarter = next(evidence for evidence in verdict.dependencies if evidence.requirement.period == "1T")
    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert first_quarter.external_evidence_kind == "aeat_csv_register"
    assert CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION in first_quarter.blockers


def test_cross_period_clean_state_accepts_live_capture_with_matching_justificante_metadata(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            evidence_kind_by_period={"1T": ExternalEvidenceKind.AEAT_LIVE_CAPTURE},
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    first_quarter = next(evidence for evidence in verdict.dependencies if evidence.requirement.period == "1T")
    assert first_quarter.external_evidence_kind == "aeat_live_capture"
    assert first_quarter.blockers == ()
    assert verdict.clean is True


def test_cross_period_clean_state_blocks_live_capture_without_justificante_verification(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            evidence_kind_by_period={"1T": ExternalEvidenceKind.AEAT_LIVE_CAPTURE},
            skip_justificante_metadata_periods={"1T"},
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    first_quarter = next(evidence for evidence in verdict.dependencies if evidence.requirement.period == "1T")
    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert first_quarter.external_evidence_kind == "aeat_live_capture"
    # AEAT_LIVE_CAPTURE is now a justificante-verified evidence kind (the captured
    # receipt is official filing evidence), so a live capture lacking the persisted
    # justificante record is blocked on the missing record rather than on the kind.
    # The safety intent — a live capture without justificante backing cannot clear a
    # dependent period — is preserved; only the blocker classification changed.
    assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_mismatched_justificante_metadata(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            skip_justificante_metadata_periods={"1T"},
        )
        _persist_justificante_metadata("JUST-1T", modelo="303", period="2T", filing_year=_M390_YEAR)

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    first_quarter = next(evidence for evidence in verdict.dependencies if evidence.requirement.period == "1T")
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_verify_modelo_revision_refuses_m390_when_prior_filings_are_not_clean(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="390",
            filing_year=_M390_YEAR,
            period=Period.from_year_and_code(_M390_YEAR, _M390_PERIOD),
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
        finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN for finding in report.findings
    )
