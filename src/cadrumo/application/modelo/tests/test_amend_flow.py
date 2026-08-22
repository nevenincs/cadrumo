"""End-to-end tests for the modelo external-filing amend path.

Every test wires the full set of catalogue repositories over a
fresh encrypted SQLite database and seeds a baseline filing record
that carries ``external_evidence`` — the gate the amend path
demands. The new revision lands as a complementaria amendment that
supersedes the baseline filing and emits a ``modelo.amended``
bucket event.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import Engine

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import AuthProviderKind, CasillaId, Period, validated_casilla_id
from ....core.config import Settings
from ....core.resources import resources
from ....domain.buckets import BucketEventType
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingInstanceEvidence,
    ModeloRecord,
    ModeloRecordStatus,
    WorkUnit,
    derive_calculation_revision_id,
    derive_filing_record_id,
    upsert_calculation_revision,
    upsert_filing_record,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ....tests.write_unit_recorder import WriteUnitRecorder
from .. import (
    AmendmentEvidenceMissingError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    CalculationRevisionStateError,
    amend_modelo_revision,
    calculate_modelo_revision,
    create_work_unit,
    get_calculation_revision,
    get_filing_record,
    get_work_unit,
    verify_modelo_revision,
)
from ._file_flow_support import (
    seed_clean_cross_period_sources,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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
def _amend_runtime(tmp_path: Path) -> Iterator[_AmendRuntime]:
    """Provision the shared ready-profile runtime used by every amend-flow test."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label=_PROFILE_LABEL) as profile:
        objects = profile.repository
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_PROFILE_ID,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
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
) -> WorkUnit:
    """Modelo 130 1T 2026 — registry-resolvable so the formula engine
    in ``calculate_modelo_revision`` has a snapshot to operate on."""

    return create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period_code),
        revision_id=revision_id,
        repository=wu_repo,
        clock=_T0,
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
) -> tuple[WorkUnit, CalculationRevision, ModeloRecord]:
    """Seed a CURRENT filing record carrying ``external_evidence`` plus
    its underlying calculation revision and work unit.

    ``member_nif`` seeds a member-scoped group-filing baseline (e.g. a 322
    imputación member) rather than a single-filer one; omitted, the baseline
    keeps the existing single-filer shape every other caller relies on."""

    wu_repo, cr_repo, fr_repo, _, _ = repos_tuple
    work_unit = _seed_work_unit(
        wu_repo,
        modelo=modelo,
        filing_year=filing_year,
        period_code=period_code,
        revision_id=revision_id_value,
    )

    inputs: dict[CasillaId, str] = {}
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
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUST-2024-303-1T-ABC123",
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
    )
    filing_repository.save(upsert_filing_record(filing_repository.load(), filing))
    return filing


def test_amend_refuses_evidence_less_m303_external_baseline(repos: _Repos) -> None:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
    _, _, baseline = _seed_external_baseline(
        repos,
        modelo="303",
        filing_year=2026,
        period_code="1T",
        revision_id_value=snapshot.revision.id,
        casilla_values={_M303_RESULT_CASILLA: Decimal("0")},
        filing_instance_evidence=None,
    )

    with pytest.raises(AmendmentEvidenceMissingError):
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_M303_RESULT_CASILLA: Decimal("1")},
            amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            reason="correction requires immutable filing evidence",
            actor="operator-A",
            work_unit_repository=repos[0],
            calculation_repository=repos[1],
            filing_repository=repos[2],
            bucket_event_repository=repos[4],
            clock=_T4,
        )


def test_amend_refuses_without_external_evidence(repos: _Repos) -> None:
    """A locally-filed return (no ``external_evidence``) cannot be amended."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
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
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
    )
    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        settings=Settings(
            cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
            cadrumo_clave_movil_dni_nie=SecretStr("X1234567L"),
        ),
        clock=_T2,
    )
    assert report.granted_verificado_completo is True
    verified_revision = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
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

    with pytest.raises(AmendmentEvidenceMissingError):
        amend_modelo_revision(
            from_filing_record_id=locally_filed.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )


def test_amend_refuses_when_baseline_already_superseded(repos: _Repos) -> None:
    """A SUPERSEDED filing record cannot be amended."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    _, _, baseline = _seed_external_baseline(repos, casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")})
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

    with pytest.raises(AmendmentTargetStateError):
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="late evidence",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
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


def _drive_amend_creates_complementaria(repos: _Repos) -> _AmendOutcome:
    """Run the seed-baseline + amend scenario and bundle the observable state."""
    wu_repo, cr_repo, fr_repo, _evidence_repo, bv_repo = repos
    work_unit, baseline_revision, baseline = _seed_external_baseline(
        repos,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000"), _AMEND_EXPENSE_CASILLA: Decimal("250")},
    )
    new_filing = amend_modelo_revision(
        from_filing_record_id=baseline.filing_record_id,
        overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="under-reported turnover discovered in audit",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    return _AmendOutcome(
        work_unit=work_unit,
        baseline_revision=baseline_revision,
        baseline=baseline,
        new_filing=new_filing,
    )


def test_amend_new_filing_is_current_complementaria_record(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    assert outcome.new_filing.status is ModeloRecordStatus.VIGENTE
    assert outcome.new_filing.amends_filing_record_id == outcome.baseline.filing_record_id
    assert outcome.new_filing.external_evidence is None


def test_amend_new_filing_records_filing_metadata(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    assert outcome.new_filing.filed_at == _T4
    assert outcome.new_filing.filed_by == "operator-A"


def test_amend_baseline_is_superseded_by_new_filing(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    _, _, fr_repo, _, _ = repos
    refreshed_baseline = get_filing_record(outcome.baseline.filing_record_id, filing_repository=fr_repo)
    assert refreshed_baseline.status is ModeloRecordStatus.SUPERSEDIDO
    assert refreshed_baseline.superseded_by_filing_record_id == outcome.new_filing.filing_record_id


def test_amend_new_revision_is_filed_complementaria(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    _, cr_repo, _, _, _ = repos
    new_revision = get_calculation_revision(outcome.new_filing.calculation_revision_id, calculation_repository=cr_repo)
    assert new_revision.state is CalculationRevisionState.PRESENTADO
    assert new_revision.amendment_identity is not None
    assert new_revision.amendment_identity.kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA
    assert new_revision.amendment_identity.amends_filing_record_id == outcome.baseline.filing_record_id
    assert new_revision.amendment_reason == "under-reported turnover discovered in audit"


def test_amend_member_scoped_filing_id_carries_member_nif(repos: _Repos) -> None:
    """A member-scoped amendment's new filing record carries the baseline's
    ``member_nif`` -- both on the persisted record and in its derived id --
    rather than silently defaulting to the single-filer ``None`` slot."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    _, _, baseline = _seed_external_baseline(
        repos,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
        member_nif="A00000000",
    )
    assert baseline.member_nif == "A00000000"

    new_filing = amend_modelo_revision(
        from_filing_record_id=baseline.filing_record_id,
        overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="member A turnover correction",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )

    assert new_filing.member_nif == "A00000000"
    assert new_filing.filing_record_id == derive_filing_record_id(
        work_unit_id=new_filing.work_unit_id,
        calculation_revision_id=new_filing.calculation_revision_id,
        filed_by="operator-A",
        member_nif="A00000000",
    )


def test_amend_member_scoped_filing_does_not_collide_with_single_filer_record(repos: _Repos) -> None:
    """Amending a member-scoped baseline must not collide with an unrelated
    single-filer VIGENTE record sharing the same (modelo, year, period).

    Reproduces the second-order ``ModeloRecordCatalogue`` hazard the
    ``member_nif`` drop caused: without it, the amendment's new filing record
    would land on the single-filer ``None`` coordinate and collide with a
    genuine single-filer current record for the same (bucket, modelo,
    filing_year, period) -- surfacing as a confusing "more than one current
    filing record" catalogue error with no path back to the missing-member
    cause."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit, _, baseline_a = _seed_external_baseline(
        repos,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
        member_nif="A00000000",
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
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), single_filer_filing))

    new_filing = amend_modelo_revision(
        from_filing_record_id=baseline_a.filing_record_id,
        overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="member A turnover correction",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )

    assert new_filing.member_nif == "A00000000"
    refreshed_single_filer = get_filing_record(single_filer_filing_id, filing_repository=fr_repo)
    assert refreshed_single_filer.status is ModeloRecordStatus.VIGENTE


def test_amend_overridden_casilla_takes_new_value(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    _, cr_repo, _, _, _ = repos
    new_revision = get_calculation_revision(outcome.new_filing.calculation_revision_id, calculation_repository=cr_repo)
    assert new_revision.casilla_values[_AMEND_INCOME_CASILLA] == Decimal("1100")


def test_amend_unoverridden_casilla_inherits_baseline_value(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    _, cr_repo, _, _, _ = repos
    new_revision = get_calculation_revision(outcome.new_filing.calculation_revision_id, calculation_repository=cr_repo)
    assert (
        new_revision.casilla_values[_AMEND_EXPENSE_CASILLA]
        == outcome.baseline_revision.casilla_values[_AMEND_EXPENSE_CASILLA]
    )


def test_amend_work_unit_pointers_advance_to_new_filing(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    wu_repo, _, _, _, _ = repos
    refreshed_wu = get_work_unit(outcome.work_unit.work_unit_id, repository=wu_repo)
    assert refreshed_wu.filed_calculation_revision_id == outcome.new_filing.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == outcome.new_filing.filing_record_id


def test_amend_emits_single_modelo_amended_event(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
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
def test_amend_amended_event_payload_records_metadata(repos: _Repos, payload_key: str, expected: str) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    _, _, _, _, bv_repo = repos
    amended_events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    assert amended_events[0].payload[payload_key] == expected


def test_amend_amended_event_targets_new_filing_record(repos: _Repos) -> None:
    outcome = _drive_amend_creates_complementaria(repos)
    _, _, _, _, bv_repo = repos
    amended_events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_AMENDED,),
    )
    event = amended_events[0]
    assert event.object_id == outcome.new_filing.filing_record_id
    assert event.payload["amends_filing_record_id"] == outcome.baseline.filing_record_id


def test_amend_refuses_no_op_overrides(repos: _Repos) -> None:
    """Overrides identical to the baseline produce the same content-
    addressed revision id; the action refuses rather than persisting
    a no-op amendment."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    _, _, baseline = _seed_external_baseline(repos, casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")})

    with pytest.raises(CalculationRevisionStateError) as exc_info:
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1000")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="duplicate filing attempt",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
    assert exc_info.value.translated_message == "errors.error.error_modelo_calculation_revision_state"


def test_amend_refuses_overrides_with_casilla_ids_not_in_registry(repos: _Repos) -> None:
    """An override targeting a casilla id the registry does not declare
    for the baseline modelo / filing_year / period is refused. The
    corrected revision is the legal basis of the complementaria filing;
    fabricated casillas cannot be silently accepted."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    _, _, baseline = _seed_external_baseline(repos, casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")})

    with pytest.raises(AmendmentOverrideCasillaError) as exc_info:
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_UNKNOWN_AMEND_CASILLA: Decimal("100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="fabricated casilla rejected",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    casillas_obj = exc_info.value.context.get("casillas", [])
    assert isinstance(casillas_obj, (list, tuple))
    assert _UNKNOWN_AMEND_CASILLA in casillas_obj


def test_amend_refuses_printed_number_metadata_token(repos: _Repos) -> None:
    """Amendment overrides must not treat a printed number as a casilla reference."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
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
        ),
    )

    with pytest.raises(AmendmentOverrideCasillaError, match="non-canonical reference tokens") as exc_info:
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_M303_PRINTED_RESULT_TOKEN: Decimal("50")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="printed number override rejected",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )

    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == [_M303_PRINTED_RESULT_TOKEN]
    assert "iva.resultado" in str(exc_info.value)


def test_amend_refuses_non_string_override_casilla_keys_without_coercion(repos: _Repos) -> None:
    """Malformed override casilla keys fail before registry membership checks."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    _, _, baseline = _seed_external_baseline(repos, casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")})

    with pytest.raises(AmendmentOverrideCasillaError) as exc_info:
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={1: Decimal("100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="malformed casilla rejected",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == ["1"]


def test_amend_revision_carries_casilla_observations(repos: _Repos) -> None:
    """The amendment revision preserves regulatory grounding.

    The amend path used to build the corrected `CalculationRevision`
    with no `observations=` argument, defaulting it to `()` — every
    complementaria/sustitutiva amendment discarded all
    `CasillaObservation` provenance. The amendment must now carry one
    typed observation per corrected casilla, synthesised from the
    registry snapshot even when the baseline revision itself carries
    no observations (the externally-imported baseline seeded here)."""

    outcome = _drive_amend_creates_complementaria(repos)
    _, cr_repo, _, _, _ = repos
    new_revision = get_calculation_revision(outcome.new_filing.calculation_revision_id, calculation_repository=cr_repo)

    observed = {obs.casilla_id: obs for obs in new_revision.observations}
    assert observed, "amendment revision persisted zero observations — provenance lost"
    assert set(observed) == set(new_revision.casilla_values)
    # the overridden casilla carries the corrected value
    assert observed[_AMEND_INCOME_CASILLA].value == Decimal("1100")
    # the non-overridden casilla carries the baseline value
    assert observed[_AMEND_EXPENSE_CASILLA].value == new_revision.casilla_values[_AMEND_EXPENSE_CASILLA]


def test_amend_baseline_carries_no_ledger_contributors(repos: _Repos) -> None:
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
    outcome = _drive_amend_creates_complementaria(repos)
    _, cr_repo, _, _, _ = repos
    new_revision = get_calculation_revision(outcome.new_filing.calculation_revision_id, calculation_repository=cr_repo)

    assert outcome.baseline_revision.source_transaction_ids == ()
    assert new_revision.source_transaction_ids == ()
    # The amendment genuinely reaches an export-admitted state with no evidence;
    # the empty contributor set is the only reason that is not a refusal.
    assert new_revision.state is CalculationRevisionState.PRESENTADO
    assert new_revision.ledger_filing_snapshot is None
    assert new_revision.ledger_filing_evidence is None


def test_export_guard_would_refuse_an_amendment_carrying_contributors(repos: _Repos) -> None:
    """The latent half: contributors without evidence IS refused.

    The sibling test pins that an amendment carries no contributors. This
    one pins what the guard does if that ever stops holding, so the pair
    states the whole invariant rather than half of it — the reachability
    fact and the consequence are recorded together.
    """
    from .._export import ModeloExportEvidenceMissingError, _raise_if_ledger_export_evidence_missing

    outcome = _drive_amend_creates_complementaria(repos)
    _, cr_repo, _, _, _ = repos
    new_revision = get_calculation_revision(outcome.new_filing.calculation_revision_id, calculation_repository=cr_repo)

    # As built, the guard passes: no contributors, so nothing to evidence.
    _raise_if_ledger_export_evidence_missing(new_revision)

    with_contributors = new_revision.model_copy(update={"source_transaction_ids": ("a" * 64,)})
    with pytest.raises(ModeloExportEvidenceMissingError):
        _raise_if_ledger_export_evidence_missing(with_contributors)


def test_amendment_commits_its_catalogues_and_event_in_one_transaction(
    amend_runtime: _AmendRuntime,
) -> None:
    """The amendment's three catalogues and its event share one transaction.

    Saved separately with ``modelo.amended`` emitted last, an event-storage
    failure left the amended filing durable and the work-unit pointers advanced
    onto it while the history had no corresponding event and no retryable
    incomplete-amendment marker named the gap.
    """
    repos_tuple = amend_runtime.repos
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos_tuple
    _, _, baseline = _seed_external_baseline(
        repos_tuple,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
    )
    recorder = WriteUnitRecorder(amend_runtime.engine)

    with recorder.recording():
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )

    assert recorder.commits_between_writes() == 0


def test_split_amendment_write_shape_commits_between_catalogues(
    amend_runtime: _AmendRuntime,
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
    )
    amend_modelo_revision(
        from_filing_record_id=baseline.filing_record_id,
        overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="under-reported turnover",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
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
    amend_runtime: _AmendRuntime,
) -> None:
    """Parity: co-committing the event does not change what an amendment records."""
    repos_tuple = amend_runtime.repos
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos_tuple
    _, _, baseline = _seed_external_baseline(
        repos_tuple,
        casilla_values={_AMEND_INCOME_CASILLA: Decimal("1000")},
    )

    amended = amend_modelo_revision(
        from_filing_record_id=baseline.filing_record_id,
        overrides={_AMEND_INCOME_CASILLA: Decimal("1100")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="under-reported turnover",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )

    refreshed = get_work_unit(baseline.work_unit_id, repository=wu_repo)
    assert refreshed.current_filing_record_id == amended.filing_record_id
    assert refreshed.filed_calculation_revision_id == amended.calculation_revision_id
    assert get_filing_record(baseline.filing_record_id, filing_repository=fr_repo).status is (
        ModeloRecordStatus.SUPERSEDIDO
    )

    amended_events = [
        event for event in bv_repo.load().events.values() if event.event_type is BucketEventType.MODELO_AMENDED
    ]
    assert len(amended_events) == 1
    assert amended_events[0].object_id == amended.filing_record_id
    assert amended_events[0].payload["amends_filing_record_id"] == baseline.filing_record_id
