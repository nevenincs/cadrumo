"""Shared real-behavior builders for cross-period clean-state tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache

from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.inbound.pdf import source_pdf_reference_path
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....core import CasillaId, Period, RegistryAuthorityGrade
from ....core.resources import bundled_path, resources
from ....domain.calculations.registry import Modelo202Modality, RegistrySnapshot
from ....domain.calculations.registry.tests import build_snapshot
from ....domain.justificante import Justificante
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloCode,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    WorkUnit,
    derive_calculation_revision_id,
    derive_filing_record_id,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_modelo_observation, registry_grounded_observations
from ....tests.registry_tree import bundled_registry_tree
from ...modelo import (
    create_work_unit,
    import_external_filing_evidence,
)
from .. import (
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyRequirement,
    CrossPeriodExpectedMemberSet,
    cross_period_dependency_requirements,
    evaluate_cross_period_clean_state,
    filing_external_evidence_blockers,
)

_PROFILE_ID = "39039039-0390-4390-8390-390390390390"
_BUCKET_ID = _PROFILE_ID
_M390_YEAR = 2025
_M390_PERIOD = "0A"
_M390_FIRST_QUARTER = Period.from_year_and_code(_M390_YEAR, "1T")
#: The law-determined revision for ``(390, _M390_YEAR, _M390_PERIOD)``. The open
#: ``2010-y-siguientes`` span was split into per-year revisions, so the pinned
#: literal named a revision the modelo no longer declares. It stays a literal
#: because the work unit only ever ASSERTS it equals the resolved revision.
_M390_REVISION = "2025"
_M353_YEAR = 2026
_M353_PERIOD = "12"
_CLOCK = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_GROUP_MEMBER_A = "A00000000"
_GROUP_MEMBER_B = "B00000000"
_GROUP_MEMBER_C = "C00000000"


def _store_ready_profile(
    *,
    bucket_id: str = _BUCKET_ID,
    profile_id: str = _PROFILE_ID,
    tax_id: str = "X1234567L",
) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=profile_id,
            facts=(
                UserProfileFact(path="identity.tax_id", value=tax_id),
                UserProfileFact(path="identity.name", value="Ready"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="test activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


@cache
def _snapshot_390() -> RegistrySnapshot:
    """Build a CALCULATION-grade snapshot directly, bypassing filing-grade admission.

    Modelo 390 carries a real fichero-BOE layout on every revision, so this
    succeeds without going through
    :class:`~domain.calculations.registry.ValidatedRegistryAuthority`, whose
    ``.load()`` validates the entire registry tree -- including modelos with no
    export layout at all -- and currently refuses unconditionally as a result.
    """
    modelos, catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "390")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_M390_YEAR,
        period=_M390_PERIOD,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def _m390_first_quarter_evidence(verdict: CrossPeriodCleanStateVerdict) -> CrossPeriodDependencyEvidence:
    return next(evidence for evidence in verdict.dependencies if evidence.requirement.period == _M390_FIRST_QUARTER)


def _source_values(period: str, source_casilla_ids: tuple[CasillaId, ...]) -> dict[CasillaId, Decimal]:
    period_ordinal = {"1T": 1, "2T": 2, "3T": 3, "4T": 4}[period]
    return {casilla_id: Decimal(period_ordinal * (index + 1)) for index, casilla_id in enumerate(source_casilla_ids)}


def _save_source_observation(
    repository: CalculationObservationRepository,
    *,
    period: str,
    source_values: dict[CasillaId, Decimal],
    source_kind: str = "aeat_sede_justificante",
    source_metadata: dict[str, str] | None = None,
) -> None:
    repository.save(
        repository.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo="303",
                filing_year=_M390_YEAR,
                period=period,
                casilla_values=source_values,
            ),
            source_kind=source_kind,
            captured_at=_CLOCK,
            source_metadata=source_metadata,
        )
    )


@cache
def _snapshot_353() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("353", filing_year=_M353_YEAR, period=_M353_PERIOD)


@cache
def _member_fan_in_requirement() -> CrossPeriodDependencyRequirement:
    return next(
        requirement
        for requirement in cross_period_dependency_requirements(_snapshot_353())
        if requirement.requires_member_fan_in
    )


def _member_source_values(member_nif: str, source_casilla_ids: tuple[CasillaId, ...]) -> dict[CasillaId, Decimal]:
    member_ordinal = {
        _GROUP_MEMBER_A: Decimal("1"),
        _GROUP_MEMBER_B: Decimal("10"),
        _GROUP_MEMBER_C: Decimal("100"),
    }[member_nif]
    return {casilla_id: member_ordinal * Decimal(index + 1) for index, casilla_id in enumerate(source_casilla_ids)}


def _save_member_322_observation(
    repository: CalculationObservationRepository,
    *,
    member_nif: str,
    source_casilla_ids: tuple[CasillaId, ...],
    source_metadata: dict[str, str] | None = None,
) -> None:
    repository.save(
        repository.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo="322",
                filing_year=_M353_YEAR,
                period=_M353_PERIOD,
                casilla_values=_member_source_values(member_nif, source_casilla_ids),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_CLOCK,
            member_nif=member_nif,
            source_metadata=source_metadata,
        )
    )


def _seed_member_322_filing(
    observation_repository: CalculationObservationRepository,
    *,
    member_nif: str,
    source_casilla_ids: tuple[CasillaId, ...],
    justificante_tax_id: str | None = None,
    source_metadata: dict[str, str] | None = None,
) -> None:
    if source_metadata is None:
        source_metadata = {
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": f"EXP-322-{_M353_YEAR}-{_M353_PERIOD}-{member_nif}",
            "authenticated_identity": member_nif,
            "aeat_justificante_csv": f"JUST322{member_nif}",
        }
    values = _member_source_values(member_nif, source_casilla_ids)
    work_unit_id = hashlib.sha256(f"322:{_M353_YEAR}:{_M353_PERIOD}:{member_nif}".encode()).hexdigest()
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=values,
        observations=registry_grounded_modelo_observation(
            modelo="322",
            filing_year=_M353_YEAR,
            period=_M353_PERIOD,
            casilla_values=values,
        ).observations,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="aeat-import-test",
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repository = CalculationRevisionCatalogueRepository()
    calculation_catalogue = calculation_repository.load()
    calculation_repository.save(
        CalculationRevisionCatalogue(revisions={**dict(calculation_catalogue.revisions), revision_id: revision}),
    )

    evidence_reference_id = f"JUST322{member_nif}"
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
        source_casilla_ids=source_casilla_ids,
        source_metadata=source_metadata,
    )


def _persist_justificante_metadata(
    csv: str,
    *,
    modelo: str,
    period: str,
    filing_year: int,
    tax_id: str = "X1234567L",
    presentation_id: str | None = None,
) -> None:
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    JustificanteRepository().save(
        Justificante(
            csv=csv,
            modelo=modelo,
            period=Period.from_year_and_code(filing_year, period),
            ejercicio=str(filing_year),
            presentation_id=presentation_id,
            presented_at=_CLOCK,
            tax_id=tax_id,
            total_a_ingresar=None,
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
            source_pdf_path=source_pdf_reference_path(source_pdf_sha256),
            source_pdf_sha256=source_pdf_sha256,
            parsed_at=_CLOCK,
        ),
    )


def _live_capture_filing(*, csv: str, kind: ExternalEvidenceKind) -> ModeloRecord:
    work_unit_id = hashlib.sha256(f"130:2026:1T:{csv}".encode()).hexdigest()
    revision_id = hashlib.sha256(f"rev:{csv}".encode()).hexdigest()
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
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


def _external_evidence_blockers(
    filing: ModeloRecord,
    source_kind: str,
    expected_tax_id: str | None = "X1234567L",
    source_metadata: dict[str, str] | None = None,
) -> list[CrossPeriodCleanStateBlocker]:
    return filing_external_evidence_blockers(
        filing,
        source_kind,
        JustificanteRepository(),
        expected_tax_id,
        source_metadata,
    )


def _seed_official_303_source_filings(
    *,
    observation_repository: CalculationObservationRepository,
    evidence_kind_by_period: dict[str, ExternalEvidenceKind] | None = None,
    omit_justificante_metadata_periods: set[str] | None = None,
    source_kind_by_period: dict[str, str] | None = None,
    source_metadata_by_period: dict[str, dict[str, str] | None] | None = None,
) -> None:
    _store_ready_profile()
    evidence_kind_by_period = evidence_kind_by_period or {}
    omit_justificante_metadata_periods = omit_justificante_metadata_periods or set()
    source_kind_by_period = source_kind_by_period or {}
    source_metadata_by_period = source_metadata_by_period or {}
    source_casilla_ids_by_period: dict[str, set[CasillaId]] = {}
    for requirement in cross_period_dependency_requirements(_snapshot_390()):
        source_casilla_ids_by_period.setdefault(
            requirement.period.registry_token,
            set(),
        ).update(requirement.source_casilla_ids)

    for period, source_casilla_ids in sorted(source_casilla_ids_by_period.items()):
        evidence_kind = evidence_kind_by_period.get(period, ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF)
        evidence_reference_id = f"JUST0000{period}"
        if (
            evidence_kind
            in {
                ExternalEvidenceKind.AEAT_CSV_REGISTER,
                ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
            }
            and period not in omit_justificante_metadata_periods
        ):
            _persist_justificante_metadata(evidence_reference_id, modelo="303", period=period, filing_year=_M390_YEAR)
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_M390_YEAR,
            period=Period.from_year_and_code(_M390_YEAR, period),
            revision_id=resources()
            .modelos.authority.snapshot(
                "303",
                filing_year=_M390_YEAR,
                period=period,
            )
            .revision.id,
            clock=_CLOCK,
        )
        values = _source_values(period, tuple(sorted(source_casilla_ids)))
        if (
            evidence_kind
            in {
                ExternalEvidenceKind.AEAT_CSV_REGISTER,
                ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
            }
            and period in omit_justificante_metadata_periods
        ):
            _seed_source_filing_record_without_import_flow(
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
        default_source_metadata = {
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": f"EXP-303-{_M390_YEAR}-{period}",
            "authenticated_identity": "X1234567L",
        }
        if (
            evidence_kind
            in {
                ExternalEvidenceKind.AEAT_CSV_REGISTER,
                ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
            }
            and period not in omit_justificante_metadata_periods
        ):
            default_source_metadata["aeat_justificante_csv"] = evidence_reference_id
        _save_source_observation(
            observation_repository,
            period=period,
            source_values=values,
            source_kind=source_kind_by_period.get(period, "aeat_sede_justificante"),
            source_metadata=source_metadata_by_period.get(period, default_source_metadata),
        )


def _seed_source_filing_record_without_import_flow(
    *,
    work_unit: WorkUnit,
    casilla_values: dict[CasillaId, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
) -> None:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
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
    )
    calculation_repository = CalculationRevisionCatalogueRepository()
    calculation_catalogue = calculation_repository.load()
    calculation_repository.save(
        CalculationRevisionCatalogue(revisions={**dict(calculation_catalogue.revisions), revision_id: revision}),
    )

    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
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


def _evaluate_clean_state(
    snapshot: RegistrySnapshot,
    *,
    observation_repository: CalculationObservationRepository | None = None,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    verification_repository: VerificationReportCatalogueRepository | None = None,
    bucket_id: str = _BUCKET_ID,
    taxpayer_tax_id: str | None = "X1234567L",
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    activity_start_date: date | None = None,
    modelo_202_modality: Modelo202Modality | None = None,
    taxpayer_files_economic_activity: bool | None = None,
    not_applicable_source_modelos: frozenset[str] | None = None,
    zero_value_previous_filing_binding_ids: frozenset[str] | None = None,
) -> CrossPeriodCleanStateVerdict:
    return evaluate_cross_period_clean_state(
        snapshot,
        bucket_id=bucket_id,
        observation_repository=observation_repository
        if observation_repository is not None
        else CalculationObservationRepository(),
        filing_repository=filing_repository if filing_repository is not None else ModeloRecordCatalogueRepository(),
        calculation_repository=calculation_repository
        if calculation_repository is not None
        else CalculationRevisionCatalogueRepository(),
        verification_repository=verification_repository
        if verification_repository is not None
        else VerificationReportCatalogueRepository(),
        taxpayer_tax_id=taxpayer_tax_id,
        expected_member_sets=expected_member_sets,
        activity_start_date=activity_start_date,
        modelo_202_modality=modelo_202_modality,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids,
    )


BUCKET_ID = _BUCKET_ID
CLOCK = _CLOCK
GROUP_MEMBER_A = _GROUP_MEMBER_A
GROUP_MEMBER_B = _GROUP_MEMBER_B
GROUP_MEMBER_C = _GROUP_MEMBER_C
M353_PERIOD = _M353_PERIOD
M353_YEAR = _M353_YEAR
M390_PERIOD = _M390_PERIOD
M390_REVISION = _M390_REVISION
M390_YEAR = _M390_YEAR
evaluate_clean_state = _evaluate_clean_state
external_evidence_blockers = _external_evidence_blockers
live_capture_filing = _live_capture_filing
m390_first_quarter_evidence = _m390_first_quarter_evidence
member_fan_in_requirement = _member_fan_in_requirement
persist_justificante_metadata = _persist_justificante_metadata
save_member_322_observation = _save_member_322_observation
seed_member_322_filing = _seed_member_322_filing
seed_official_303_source_filings = _seed_official_303_source_filings
snapshot_353 = _snapshot_353
snapshot_390 = _snapshot_390
store_ready_profile = _store_ready_profile
