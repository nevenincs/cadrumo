"""End-to-end tests for the modelo external-filing amend path.

Every test wires the full set of catalogue repositories over a
fresh encrypted SQLite database and seeds a baseline filing record
that carries ``external_evidence`` — the gate the amend path
demands. The new revision lands as a complementaria amendment that
supersedes the baseline filing and emits a ``modelo.amended``
bucket event.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, SecretStr, TypeAdapter
from sqlalchemy.engine import Engine

from cadrumo.adapters.inbound.pdf.source_provenance import source_pdf_reference_path
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.domain.justificante.schema import Justificante
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.tests.aeat_literal_fixtures import justificante_cotejo_url

from ....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ....application.modelo.action_errors import (
    AmendmentEvidenceMissingError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    CalculationRevisionStateError,
    StoredRowFieldScalarInputError,
)
from ....application.modelo.amendment_actions import amend_modelo_revision
from ....application.modelo.calculation_actions import calculate_modelo_revision, get_calculation_revision
from ....application.modelo.export import (
    ModeloExportCommand,
    ModeloExportEvidenceMissingError,
    export_modelo_revision,
)
from ....application.modelo.filing_actions import get_filing_record
from ....application.modelo.verification_actions import verify_modelo_revision
from ....application.modelo.work_lifecycle import (
    create_work_unit,
    get_work_unit,
)
from ....core.auth_provider import AuthProviderKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.config import Settings
from ....core.period import Period
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
)
from ....domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.filing_repository import upsert_filing_record
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ...adapter_composition import (
    build_amendment_action_ports,
    build_calculation_action_ports,
    build_filing_action_ports,
    build_work_lifecycle_ports,
)
from ....tests.write_unit_recorder import WriteUnitRecorder
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
from .file_flow_test_support import (
    workflow_profile,
)
from ....adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

type _Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 1, 15, 14, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 15, 15, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_PROFILE_ID = "10000000-0000-4000-8000-000000000130"
_PROFILE_LABEL = "Test runtime profile"
_READY_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="X1234567L"),
    UserProfileFact(path="identity.name", value="Ready"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="file-flow"),
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
)


_AMEND_INCOME_CASILLA: CasillaId = validated_casilla_id("01")
_AMEND_EXPENSE_CASILLA: CasillaId = validated_casilla_id("02")
_AMEND_WITHHELD_CASILLA: CasillaId = validated_casilla_id("05")
_AMEND_PREVIOUS_PAYMENT_CASILLA: CasillaId = validated_casilla_id("06")
_AMEND_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_AMEND_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_AMEND_CARRY_FORWARD_CASILLA: CasillaId = validated_casilla_id("15")
_AMEND_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_AMEND_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
_UNKNOWN_AMEND_CASILLA: CasillaId = validated_casilla_id("9999")
_M303_RESULT_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_PRINTED_RESULT_TOKEN: CasillaId = validated_casilla_id("69")


@dataclass(frozen=True, slots=True)
class _AmendRuntime:
    """The live engine plus the repository bundle sharing it."""

    engine: Engine
    repos: _Repos


@contextmanager
def _amend_runtime(tmp_path: Path) -> Generator[_AmendRuntime]:
    """Provision the shared ready-profile runtime used by every amend-flow test."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label=_PROFILE_LABEL) as profile:
        objects = profile.repository
        with bundled_indexed_authority().operation():
            seed_test_profile_record(
                _create_profile_record_for_test(
                    setup_state=ProfileSetupState.COMPLETE,
                    profile_id=_PROFILE_ID,
                    facts=_READY_PROFILE_FACTS,
                    created_at=_T0,
                    updated_at=_T0,
                    context=_profile_creation_context_for_test(),
                ),
            )
        yield _AmendRuntime(
            engine=objects.engine,
            repos=(
                WorkUnitCatalogueRepository(objects=objects),
                CalculationRevisionCatalogueRepository(objects=objects),
                ModeloRecordCatalogueRepository(objects=objects),
                VerificationReportCatalogueRepository(objects=objects),
                BucketEventHistoryRepository(objects=objects),
            ),
        )


@pytest.fixture
def repos(tmp_path: Path) -> Generator[_Repos]:
    """Yield the shared ready-profile repository bundle for amend-flow tests."""

    with _amend_runtime(tmp_path) as runtime:
        yield runtime.repos


@pytest.fixture
def amend_runtime(tmp_path: Path) -> Generator[_AmendRuntime]:
    """Yield the same bundle plus the live engine, for write-unit observation."""

    with _amend_runtime(tmp_path) as runtime:
        yield runtime


def _seed_work_unit(
    wu_repo: WorkUnitCatalogueRepository,
    *,
    modelo: str = "130",
    filing_year: int = 2026,
    period_code: str = "1T",
    revision_id: str = "2019-y-siguientes",
    operation: PinnedAuthorityOperation,
) -> WorkUnit:
    """Modelo 130 1T 2026 — registry-resolvable so the formula engine
    in ``calculate_modelo_revision`` has a snapshot to operate on."""

    return create_work_unit(
        ports=build_work_lifecycle_ports(bucket_id=_PROFILE_ID),
        bucket_id=_PROFILE_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period_code),
        revision_id=revision_id,
        clock=_T0,
        operation=operation,
    )


_DEFAULT_130_BINDING_VALUES = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
}


def _seed_external_baseline(
    repos_tuple: _Repos,
    *,
    casilla_values: dict[CasillaId, Decimal],
    modelo: str = "130",
    filing_year: int = 2026,
    period_code: str = "1T",
    revision_id_value: str = "2019-y-siguientes",
    member_nif: str | None = None,
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    input_values_by_casilla_id: dict[CasillaId, str] | None = None,
    operation: PinnedAuthorityOperation,
) -> tuple[WorkUnit, CalculationRevision, ModeloRecord]:
    """Seed a CURRENT filing record carrying ``external_evidence`` plus
    its underlying calculation revision and work unit.

    ``member_nif`` seeds a member-scoped group-filing baseline (e.g. a 322
    imputación member) rather than a single-filer one; omitted, the baseline
    keeps the existing single-filer shape every other caller relies on.
    ``input_values_by_casilla_id`` seeds stored operator inputs, as a revision
    saved under earlier calculate rules may hold; omitted, it stores none."""

    wu_repo, cr_repo, fr_repo, _, _ = repos_tuple
    work_unit = _seed_work_unit(
        wu_repo,
        modelo=modelo,
        filing_year=filing_year,
        period_code=period_code,
        revision_id=revision_id_value,
        operation=operation,
    )

    inputs: dict[CasillaId, str] = {} if input_values_by_casilla_id is None else dict(input_values_by_casilla_id)
    overrides_map: dict[str, str] = {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides=overrides_map,
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat-import",
        member_nif=member_nif,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id=inputs,
        binding_overrides=overrides_map,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        created_at=_T1,
        updated_at=_T1,
        verified_at=_T1,
        verified_by="aeat-import",
        filed_at=_T1,
        filed_by="aeat-import",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

    baseline_filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        member_nif=member_nif,
        filed_at=_T1,
        filed_by="aeat-import",
        notes=None,
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUST2024303ABC123",
            imported_at=_T1,
        ),
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), baseline_filing))

    return work_unit, revision, baseline_filing


def _seed_local_filing_record(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    filed_at: datetime,
    filed_by: str,
) -> ModeloRecord:
    filed_revision = revision.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": filed_at,
            "filed_by": filed_by,
            "updated_at": filed_at,
        },
    )
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), filed_revision))
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=filed_revision.calculation_revision_id,
        filed_by=filed_by,
    )
    filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=filed_revision.calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=filed_at,
        filed_by=filed_by,
        external_evidence=None,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    filing_repository.save(upsert_filing_record(filing_repository.load(), filing))
    return filing


def test_amend_refuses_evidence_less_m303_external_baseline(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    snapshot = published_authority_operation().snapshot("303", filing_year=2026, period="1T")
    _, _, baseline = _seed_external_baseline(
        repos,
        modelo="303",
        filing_year=2026,
        period_code="1T",
        revision_id_value=snapshot.revision.id,
        casilla_values={_M303_RESULT_CASILLA: Decimal("0")},
        filing_instance_evidence=None,
        operation=operation,
    )

    with pytest.raises(AmendmentEvidenceMissingError), bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_M303_RESULT_CASILLA: Decimal("1")},
            amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            reason="correction requires immutable filing evidence",
            actor="operator-A",
            clock=_T4,
        )


def test_amend_refuses_without_external_evidence(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """A locally-filed return (no ``external_evidence``) cannot be amended."""

    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo, operation=operation)
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            actor="operator-A",
            casilla_inputs={
                _AMEND_INCOME_CASILLA: Decimal("1000"),
                _AMEND_EXPENSE_CASILLA: Decimal("0"),
                _AMEND_WITHHELD_CASILLA: Decimal("0"),
                _AMEND_PREVIOUS_PAYMENT_CASILLA: Decimal("0"),
                _AMEND_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
                _AMEND_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
                _AMEND_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _AMEND_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
            },
            binding_values=_DEFAULT_130_BINDING_VALUES,
            clock=_T1,
        )
    seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="operator-A",
            workflow_profile=workflow_profile(),
            settings=Settings(
                cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                cadrumo_clave_movil_dni_nie=SecretStr("X1234567L"),
            ),
            clock=_T2,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
    assert report.granted_verificado_completo is True
    with bundled_indexed_authority().operation() as operation:
        verified_revision = get_calculation_revision(
            revision.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )
    locally_filed = _seed_local_filing_record(
        work_unit=work_unit,
        revision=verified_revision,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        filed_at=_T3,
        filed_by="operator-A",
    )
    assert locally_filed.external_evidence is None

    with pytest.raises(AmendmentEvidenceMissingError), bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=locally_filed.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            clock=_T4,
        )


def test_amend_refuses_when_baseline_already_superseded(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """A SUPERSEDED filing record cannot be amended."""

    _wu_repo, _cr_repo, fr_repo, _, _bv_repo = repos
    _, _, baseline = _seed_external_baseline(
        repos, casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")}, operation=operation
    )
    successor_record_id = "f" * 64
    fr_repo.save(
        upsert_filing_record(
            fr_repo.load(),
            baseline.model_copy(
                update={
                    "status": ModeloRecordStatus.SUPERSEDIDO,
                    "superseded_at": _T3,
                    "superseded_by_filing_record_id": successor_record_id,
                },
            ),
        ),
    )

    with pytest.raises(AmendmentTargetStateError), bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="late evidence",
            actor="operator-A",
            clock=_T4,
        )


@dataclass(frozen=True, slots=True)
class _AmendOutcome:
    """Bundle returned by _drive_amend_creates_complementaria.

    Holds every state slice the focused tests inspect:
    work_unit + baseline + baseline_revision + the new filing
    record produced by ``amend_modelo_revision``.
    """

    work_unit: WorkUnit
    baseline_revision: CalculationRevision
    baseline: ModeloRecord
    new_filing: ModeloRecord


def _drive_amend_creates_complementaria(repos: _Repos, *, operation: PinnedAuthorityOperation) -> _AmendOutcome:
    """Run the seed-baseline + amend scenario and bundle the observable state."""
    _wu_repo, _cr_repo, _fr_repo, _evidence_repo, _bv_repo = repos
    work_unit, baseline_revision, baseline = _seed_external_baseline(
        repos,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000"), _AMEND_EXPENSE_CASILLA: Decimal("250")},
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        new_filing = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported turnover discovered in audit",
            actor="operator-A",
            clock=_T4,
        )
    return _AmendOutcome(
        work_unit=work_unit,
        baseline_revision=baseline_revision,
        baseline=baseline,
        new_filing=new_filing,
    )


def test_amend_new_filing_is_current_complementaria_record(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    assert outcome.new_filing.status is ModeloRecordStatus.VIGENTE
    assert outcome.new_filing.amends_filing_record_id == outcome.baseline.filing_record_id
    assert outcome.new_filing.external_evidence is None


def test_amend_new_filing_records_filing_metadata(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    assert outcome.new_filing.filed_at == _T4
    assert outcome.new_filing.filed_by == "operator-A"


def test_amend_baseline_is_superseded_by_new_filing(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _, _fr_repo, _, _ = repos
    refreshed_baseline = get_filing_record(
        outcome.baseline.filing_record_id,
        ports=build_filing_action_ports(bucket_id=_PROFILE_ID),
    )
    assert refreshed_baseline.status is ModeloRecordStatus.SUPERSEDIDO
    assert refreshed_baseline.superseded_by_filing_record_id == outcome.new_filing.filing_record_id


def test_amend_new_revision_is_filed_complementaria(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )
        assert new_revision.state is CalculationRevisionState.PRESENTADO
    assert new_revision.amendment_identity is not None
    assert new_revision.amendment_identity.kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA
    assert new_revision.amendment_identity.amends_filing_record_id == outcome.baseline.filing_record_id
    assert new_revision.amendment_reason == "under-reported turnover discovered in audit"


def test_amend_member_scoped_filing_id_carries_member_nif(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A member-scoped amendment's new filing record carries the baseline's
    ``member_nif`` -- both on the persisted record and in its derived id --
    rather than silently defaulting to the single-filer ``None`` slot."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = _seed_external_baseline(
        repos,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
        member_nif="A00000000",
        operation=operation,
    )
    assert baseline.member_nif == "A00000000"

    with bundled_indexed_authority().operation() as operation:
        new_filing = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="member A turnover correction",
            actor="operator-A",
            clock=_T4,
        )

    assert new_filing.member_nif == "A00000000"
    assert new_filing.filing_record_id == derive_filing_record_id(
        work_unit_id=new_filing.work_unit_id,
        calculation_revision_id=new_filing.calculation_revision_id,
        filed_by="operator-A",
        member_nif="A00000000",
    )


def test_amend_member_scoped_filing_does_not_collide_with_single_filer_record(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Amending a member-scoped baseline must not collide with an unrelated
    single-filer VIGENTE record sharing the same (modelo, year, period).

    Reproduces the second-order ``ModeloRecordCatalogue`` hazard the
    ``member_nif`` drop caused: without it, the amendment's new filing record
    would land on the single-filer ``None`` coordinate and collide with a
    genuine single-filer current record for the same (bucket, modelo,
    filing_year, period) -- surfacing as a confusing "more than one current
    filing record" catalogue error with no path back to the missing-member
    cause."""

    _wu_repo, _cr_repo, fr_repo, _, _bv_repo = repos
    work_unit, _, baseline_a = _seed_external_baseline(
        repos,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
        member_nif="A00000000",
        operation=operation,
    )

    single_filer_revision_id = "b" * 64
    single_filer_filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=single_filer_revision_id,
        filed_by="aeat-import",
    )
    single_filer_filing = ModeloRecord(
        filing_record_id=single_filer_filing_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=single_filer_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=_T1,
        filed_by="aeat-import",
        status=ModeloRecordStatus.VIGENTE,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), single_filer_filing))

    with bundled_indexed_authority().operation() as operation:
        new_filing = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline_a.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="member A turnover correction",
            actor="operator-A",
            clock=_T4,
        )

    assert new_filing.member_nif == "A00000000"
    refreshed_single_filer = get_filing_record(
        single_filer_filing_id,
        ports=build_filing_action_ports(bucket_id=_PROFILE_ID),
    )
    assert refreshed_single_filer.status is ModeloRecordStatus.VIGENTE


def test_amend_overridden_casilla_takes_new_value(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )
        assert new_revision.casilla_values[_AMEND_INCOME_CASILLA] == Decimal("1100")


def test_amend_unoverridden_casilla_inherits_baseline_value(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )
        assert (
            new_revision.casilla_values[_AMEND_EXPENSE_CASILLA]
            == outcome.baseline_revision.casilla_values[_AMEND_EXPENSE_CASILLA]
        )


def test_amend_work_unit_pointers_advance_to_new_filing(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _wu_repo, _, _, _, _ = repos
    refreshed_wu = get_work_unit(
        outcome.work_unit.work_unit_id,
        ports=build_work_lifecycle_ports(bucket_id=_PROFILE_ID),
    )
    assert refreshed_wu.filed_calculation_revision_id == outcome.new_filing.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == outcome.new_filing.filing_record_id


def test_amend_emits_single_modelo_amended_event(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _, _, _, bv_repo = repos
    amended_events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    assert len(amended_events) == 1


_AMENDED_EVENT_PAYLOAD_EXPECTATIONS = (
    ("amendment_kind", "complementaria"),
    ("override_count", "1"),
)


@pytest.mark.parametrize(("payload_key", "expected"), _AMENDED_EVENT_PAYLOAD_EXPECTATIONS)
def test_amend_amended_event_payload_records_metadata(
    repos: _Repos, payload_key: str, expected: str, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _, _, _, bv_repo = repos
    amended_events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    assert amended_events[0].payload[payload_key] == expected


def test_amend_amended_event_targets_new_filing_record(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _, _, _, bv_repo = repos
    amended_events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    event = amended_events[0]
    assert event.object_id == outcome.new_filing.filing_record_id
    assert event.payload["amends_filing_record_id"] == outcome.baseline.filing_record_id


def test_amend_refuses_no_op_overrides(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """Overrides identical to the baseline produce the same content-
    addressed revision id; the action refuses rather than persisting
    a no-op amendment."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = _seed_external_baseline(
        repos, casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")}, operation=operation
    )

    with pytest.raises(CalculationRevisionStateError) as exc_info, bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1000")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="duplicate filing attempt",
            actor="operator-A",
            clock=_T4,
        )
    assert exc_info.value.translated_message == "errors.error.error_modelo_calculation_revision_state"


def test_amend_refuses_overrides_with_casilla_ids_not_in_registry(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """An override targeting a casilla id the registry does not declare
    for the baseline modelo / filing_year / period is refused. The
    corrected revision is the legal basis of the complementaria filing;
    fabricated casillas cannot be silently accepted."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = _seed_external_baseline(
        repos, casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")}, operation=operation
    )

    with pytest.raises(AmendmentOverrideCasillaError) as exc_info, bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_UNKNOWN_AMEND_CASILLA: Decimal("100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="fabricated casilla rejected",
            actor="operator-A",
            clock=_T4,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    casillas_obj = exc_info.value.context.get("casillas", [])
    assert isinstance(casillas_obj, (list, tuple))
    assert _UNKNOWN_AMEND_CASILLA in casillas_obj


def test_amend_refuses_printed_number_metadata_token(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """Amendment overrides must not treat a printed number as a casilla reference."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = _seed_external_baseline(
        repos,
        modelo="303",
        filing_year=2025,
        period_code="1T",
        revision_id_value="2025",
        casilla_values={_M303_RESULT_CASILLA: Decimal("100")},
        filing_instance_evidence=general_m303_filing_evidence(
            Period.from_year_and_code(2025, "1T"),
            reference="test:amend:printed-token",
            operation=operation,
        ),
        operation=operation,
    )

    with (
        pytest.raises(AmendmentOverrideCasillaError, match="non-canonical reference tokens") as exc_info,
        bundled_indexed_authority().operation() as operation,
    ):
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_M303_PRINTED_RESULT_TOKEN: Decimal("50")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="printed number override rejected",
            actor="operator-A",
            clock=_T4,
        )

    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == [_M303_PRINTED_RESULT_TOKEN]
    assert "iva.resultado" in str(exc_info.value)


def test_amend_refuses_non_string_override_casilla_keys_without_coercion(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Malformed override casilla keys fail before registry membership checks."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = _seed_external_baseline(
        repos, casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")}, operation=operation
    )

    with pytest.raises(AmendmentOverrideCasillaError) as exc_info, bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={1: Decimal("100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="malformed casilla rejected",
            actor="operator-A",
            clock=_T4,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == ["1"]


def test_amend_revision_carries_casilla_observations(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """The amendment revision preserves regulatory grounding.

    The amend path used to build the corrected `CalculationRevision`
    with no `observations=` argument, defaulting it to `()` — every
    complementaria/sustitutiva amendment discarded all
    `CasillaObservation` provenance. The amendment must now carry one
    typed observation per corrected casilla, synthesised from the
    registry snapshot even when the baseline revision itself carries
    no observations (the externally-imported baseline seeded here)."""

    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )

    observed = {obs.casilla_id: obs for obs in new_revision.observations}
    assert observed, "amendment revision persisted zero observations — provenance lost"
    assert set(observed) == set(new_revision.casilla_values)
    # the overridden casilla carries the corrected value
    assert observed[_AMEND_INCOME_CASILLA].value == Decimal("1100")
    # the non-overridden casilla carries the baseline value
    assert observed[_AMEND_EXPENSE_CASILLA].value == new_revision.casilla_values[_AMEND_EXPENSE_CASILLA]


def test_amend_baseline_carries_no_ledger_contributors(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """An amendment baseline is an imported filing, so it has no ledger rows.

    This pins the fact the export evidence guard silently depends on. The
    amend path mints its own BORRADOR -> VERIFICADO_COMPLETO -> PRESENTADO
    transitions in-process and never calls ``verify_modelo_revision``, so
    ``_persist_verified_revision_evidence`` — which lives inside verify's
    granted branch — never runs for an amendment. An amendment therefore
    reaches an export-admitted state carrying neither snapshot nor bundle.

    That is only safe because the amendment also carries no
    ``source_transaction_ids``: the export guard returns early on an empty
    contributor set, so it never reaches the refusal. The emptiness is
    structural rather than incidental — ``amend_modelo_revision`` refuses a
    baseline without ``external_evidence``, and the external-import path
    builds its revision without contributors — but nothing asserted it, and
    the safety of a filing-grade guard should not rest on an unstated
    property of a different module.

    If a future path lets an imported baseline carry ledger contributors,
    this fails, and it should: that amendment would reach export with
    contributors and no evidence, which the guard refuses. The fix then
    belongs on the amend path, not on the guard.
    """
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )

    assert outcome.baseline_revision.source_transaction_ids == ()
    assert new_revision.source_transaction_ids == ()
    # The amendment genuinely reaches an export-admitted state with no evidence;
    # the empty contributor set is the only reason that is not a refusal.
    assert new_revision.state is CalculationRevisionState.PRESENTADO
    assert new_revision.ledger_filing_snapshot is None
    assert new_revision.ledger_filing_evidence is None


def _persist_baseline_justificante(baseline: ModeloRecord, *, tax_id: str) -> None:
    evidence = baseline.external_evidence
    assert evidence is not None
    pdf_sha256 = hashlib.sha256(f"justificante {evidence.reference_id}".encode()).hexdigest()
    with bundled_indexed_authority().operation():
        JustificanteRepository().save(
            Justificante(
                csv=evidence.reference_id,
                modelo=str(baseline.modelo),
                period=baseline.period,
                ejercicio=str(baseline.filing_year),
                presentation_id="1300000000001",
                presented_at=baseline.filed_at,
                tax_id=tax_id,
                total_a_ingresar=None,
                total_a_devolver=None,
                verification_url=TypeAdapter(AnyHttpUrl).validate_python(
                    justificante_cotejo_url(evidence.reference_id)
                ),
                source_pdf_path=source_pdf_reference_path(pdf_sha256),
                source_pdf_sha256=pdf_sha256,
                parsed_at=baseline.filed_at,
            ),
        )


def test_export_refuses_an_amendment_carrying_contributors(
    repos: _Repos, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The latent half: contributors without evidence IS refused.

    The sibling test pins that an amendment carries no contributors. This
    one pins what the export action does if that ever stops holding, so the pair
    states the whole invariant rather than half of it — the reachability
    fact and the consequence are recorded together.
    """
    outcome = _drive_amend_creates_complementaria(repos, operation=operation)
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    # The amended baseline is AEAT-accepted, so its receipt is on file: the
    # export reaches the contributor check rather than stopping at the receipt.
    _persist_baseline_justificante(outcome.baseline, tax_id=workflow_profile().tax_id)
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )

    contributed = new_revision.model_copy(update={"source_transaction_ids": ("a" * 64,)})
    # The contributor set is part of the content-addressed identity.
    with_contributors = contributed.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(contributed)}
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), with_contributors))

    # Exercise the public export boundary: the persisted revision has no ledger
    # snapshot/evidence for its contributor, so export must refuse before bytes
    # are rendered or written.
    with pytest.raises(ModeloExportEvidenceMissingError), bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=with_contributors.calculation_revision_id,
                output_path=tmp_path / "refused-amendment-export.txt",
                actor="operator-A",
            ),
            workflow_profile=workflow_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=_PROFILE_ID,
                calculation=cr_repo,
                work_unit=wu_repo,
                filing=fr_repo,
                bucket_event=bv_repo,
            ),
            clock=_T4,
            operation=operation,
        )


def test_amendment_commits_its_catalogues_and_event_in_one_transaction(
    amend_runtime: _AmendRuntime, *, operation: PinnedAuthorityOperation
) -> None:
    """The amendment's three catalogues and its event share one transaction.

    Saved separately with ``modelo.amended`` emitted last, an event-storage
    failure left the amended filing durable and the work-unit pointers advanced
    onto it while the history had no corresponding event and no retryable
    incomplete-amendment marker named the gap.
    """
    repos_tuple = amend_runtime.repos
    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos_tuple
    _, _, baseline = _seed_external_baseline(
        repos_tuple,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
        operation=operation,
    )
    recorder = WriteUnitRecorder(amend_runtime.engine)

    with recorder.recording(), bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            clock=_T4,
        )

    assert recorder.commits_between_writes() == 0


def test_split_amendment_write_shape_commits_between_catalogues(
    amend_runtime: _AmendRuntime, *, operation: PinnedAuthorityOperation
) -> None:
    """Anti-tautology: the recorder does report a seam when one exists.

    Persisting the same catalogues through independent saves -- the shape the
    amendment path replaced -- must be observed as more than one transaction.
    """
    repos_tuple = amend_runtime.repos
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos_tuple
    _, _, baseline = _seed_external_baseline(
        repos_tuple,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            clock=_T4,
        )
    revisions = cr_repo.load()
    filings = fr_repo.load()
    work_units = wu_repo.load()
    events = bv_repo.load()
    recorder = WriteUnitRecorder(amend_runtime.engine)

    with recorder.recording():
        cr_repo.save(revisions)
        fr_repo.save(filings)
        wu_repo.save(work_units)
        bv_repo.save(events)

    assert recorder.commits_between_writes() >= 1


def test_amendment_event_and_state_are_both_present_after_success(
    amend_runtime: _AmendRuntime, *, operation: PinnedAuthorityOperation
) -> None:
    """Parity: co-committing the event does not change what an amendment records."""
    repos_tuple = amend_runtime.repos
    _wu_repo, _cr_repo, _fr_repo, _, bv_repo = repos_tuple
    _, _, baseline = _seed_external_baseline(
        repos_tuple,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
        operation=operation,
    )

    with bundled_indexed_authority().operation() as operation:
        amended = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            clock=_T4,
        )

    refreshed = get_work_unit(
        baseline.work_unit_id,
        ports=build_work_lifecycle_ports(bucket_id=_PROFILE_ID),
    )
    assert refreshed.current_filing_record_id == amended.filing_record_id
    assert refreshed.filed_calculation_revision_id == amended.calculation_revision_id
    assert (
        get_filing_record(
            baseline.filing_record_id,
            ports=build_filing_action_ports(bucket_id=_PROFILE_ID),
        ).status
        is ModeloRecordStatus.SUPERSEDIDO
    )

    amended_events = [
        event for event in bv_repo.load().events.values() if event.event_type is BucketEventType.MODELO_AMENDED
    ]
    assert len(amended_events) == 1
    assert amended_events[0].object_id == amended.filing_record_id
    assert amended_events[0].payload["amends_filing_record_id"] == baseline.filing_record_id


def test_amend_refuses_a_baseline_saved_with_a_scalar_row_field_input(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A filed revision that stores one scalar for a per-row casilla cannot seed a correction.

    Calculate now refuses such an input. A revision filed before it did holds
    an operator input no observation explains, and the correction would carry
    it forward, so amend refuses and names the work unit to recalculate.
    """
    row_field = validated_casilla_id("perc.retenciones")
    work_unit, revision, baseline = _seed_external_baseline(
        repos,
        casilla_values={validated_casilla_id("decl.total-perceptores"): Decimal("1")},
        modelo="180",
        filing_year=2024,
        period_code="0A",
        revision_id_value="2023-y-siguientes",
        input_values_by_casilla_id={row_field: "150"},
        operation=operation,
    )

    with (
        pytest.raises(StoredRowFieldScalarInputError) as exc_info,
        bundled_indexed_authority().operation() as amend_operation,
    ):
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=amend_operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={validated_casilla_id("decl.total-perceptores"): Decimal("2")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="baseline stored a per-row value as a scalar",
            actor="operator-A",
            clock=_T4,
        )

    assert exc_info.value.translated_message == "errors.refused.refused_modelo_stored_row_field_input"
    assert exc_info.value.context == {
        "casilla_ids": row_field,
        "calculation_revision_id": revision.calculation_revision_id,
        "work_unit_id": work_unit.work_unit_id,
    }


def test_amend_does_not_demand_row_field_casillas_as_scalars(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A clean Modelo 180 correction passes the completeness gate without per-row scalars.

    Every required manual casilla Modelo 180 declares is a perceptor-row field,
    so a gate demanding them as scalars would refuse every 180 correction,
    including one whose baseline stores nothing it should not.
    """
    _work_unit, _revision, baseline = _seed_external_baseline(
        repos,
        casilla_values={validated_casilla_id("decl.total-perceptores"): Decimal("1")},
        modelo="180",
        filing_year=2024,
        period_code="0A",
        revision_id_value="2023-y-siguientes",
        operation=operation,
    )

    with bundled_indexed_authority().operation() as amend_operation:
        amended = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=amend_operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={validated_casilla_id("decl.total-perceptores"): Decimal("2")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="one more perceptor",
            actor="operator-A",
            clock=_T4,
        )

    assert amended is not None
