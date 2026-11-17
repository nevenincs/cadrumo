"""Shared runtime, fixtures and seeders for the modelo amend-flow tests."""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.amendment_actions import amend_modelo_revision
from ....application.modelo.work_lifecycle import (
    create_work_unit,
)
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import (
    published_selected_revision_id,
    published_supported_filing_years,
)
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ....domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
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
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition_work_ports import (
    build_amendment_action_ports,
    build_work_lifecycle_ports,
)

type Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]


def supported_years() -> tuple[int, int, int]:
    """Return the envelope horizon and the two filing years beneath it, all inside the envelope."""
    envelope = published_supported_filing_years()
    assert envelope is not None
    horizon = envelope.horizon
    assert envelope.floor <= horizon - 2, "the module needs two supported filing years beneath the horizon"
    return horizon, horizon - 1, horizon - 2


YEAR, PRIOR_YEAR, EARLIER_YEAR = supported_years()
T0 = datetime(YEAR, 1, 15, 12, 0, 0, tzinfo=UTC)
T1 = datetime(YEAR, 1, 15, 13, 0, 0, tzinfo=UTC)
T2 = datetime(YEAR, 1, 15, 14, 0, 0, tzinfo=UTC)
T3 = datetime(YEAR, 4, 15, 15, 0, 0, tzinfo=UTC)
T4 = datetime(YEAR, 4, 16, 12, 0, 0, tzinfo=UTC)
PROFILE_ID = "10000000-0000-4000-8000-000000000130"
PROFILE_LABEL = "Test runtime profile"
READY_PROFILE_FACTS = persona_facts_beneath(
    (
        UserProfileFact(path="identity.tax_id", value="X0001500M"),
        UserProfileFact(path="identity.name", value="Ready"),
        UserProfileFact(path="identity.surnames", value="Operator"),
        UserProfileFact(path="activities.description", value="file-flow"),
        # The taxpayer pays rent with retencion, so Modelo 180 applies to the profile.
        UserProfileFact(path="withholding.pays_rent_with_retencion", value=True),
    )
)


AMEND_INCOME_CASILLA: CasillaId = validated_casilla_id("01")
AMEND_EXPENSE_CASILLA: CasillaId = validated_casilla_id("02")
AMEND_WITHHELD_CASILLA: CasillaId = validated_casilla_id("05")
AMEND_PREVIOUS_PAYMENT_CASILLA: CasillaId = validated_casilla_id("06")
AMEND_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
AMEND_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
AMEND_CARRY_FORWARD_CASILLA: CasillaId = validated_casilla_id("15")
AMEND_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
AMEND_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
UNKNOWN_AMEND_CASILLA: CasillaId = validated_casilla_id("9999")
M303_RESULT_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
M303_PRINTED_RESULT_TOKEN: CasillaId = validated_casilla_id("69")


@dataclass(frozen=True, slots=True)
class AmendRuntime:
    """The live engine plus the repository bundle sharing it."""

    engine: Engine
    repos: Repos


@contextmanager
def provision_amend_runtime(tmp_path: Path) -> Generator[AmendRuntime]:
    """Provision the shared ready-profile runtime used by every amend-flow test."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=PROFILE_ID, label=PROFILE_LABEL) as profile:
        objects = profile.repository
        with bundled_indexed_authority().operation():
            seed_test_profile_record(
                create_user_profile_record(
                    setup_state=ProfileSetupState.COMPLETE,
                    profile_id=PROFILE_ID,
                    facts=READY_PROFILE_FACTS,
                    created_at=T0,
                    updated_at=T0,
                    context=profile_creation_context_for_test(),
                ),
            )
        yield AmendRuntime(
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
def repos(tmp_path: Path) -> Generator[Repos]:
    """Yield the shared ready-profile repository bundle for amend-flow tests."""

    with provision_amend_runtime(tmp_path) as runtime:
        yield runtime.repos


@pytest.fixture
def amend_runtime(tmp_path: Path) -> Generator[AmendRuntime]:
    """Yield the same bundle plus the live engine, for write-unit observation."""

    with provision_amend_runtime(tmp_path) as runtime:
        yield runtime


def seed_work_unit(
    wu_repo: WorkUnitCatalogueRepository,
    *,
    modelo: str = "130",
    filing_year: int = YEAR,
    period_code: str = "1T",
    revision_id: str | None = None,
    operation: PinnedAuthorityOperation,
) -> WorkUnit:
    """Modelo 130 1T of the envelope horizon -- registry-resolvable so the formula engine
    in ``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`` has a snapshot to operate on."""
    if revision_id is None:
        revision_id = published_selected_revision_id(modelo, filing_year=filing_year, period=period_code)

    return create_work_unit(
        ports=build_work_lifecycle_ports(bucket_id=PROFILE_ID),
        bucket_id=PROFILE_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period_code),
        revision_id=revision_id,
        clock=T0,
        operation=operation,
    )


def seed_external_baseline(
    repos_tuple: Repos,
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    modelo: str = "130",
    filing_year: int = YEAR,
    period_code: str = "1T",
    revision_id_value: str | None = None,
    member_nif: str | None = None,
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    input_values_by_casilla_id: dict[CasillaId, str] | None = None,
    binding_overrides: dict[str, str] | None = None,
    observations: tuple[CasillaObservation, ...] | None = None,
    operator_layer: CalculationOperatorLayer | None = None,
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
    work_unit = seed_work_unit(
        wu_repo,
        modelo=modelo,
        filing_year=filing_year,
        period_code=period_code,
        revision_id=revision_id_value,
        operation=operation,
    )

    inputs: dict[CasillaId, str] = {} if input_values_by_casilla_id is None else dict(input_values_by_casilla_id)
    overrides_map: dict[str, str] = {} if binding_overrides is None else dict(binding_overrides)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides=overrides_map,
        casilla_values=casilla_values,
        operator_layer=operator_layer,
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
        observations=observations
        or registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        operator_layer=operator_layer,
        created_at=T1,
        updated_at=T1,
        verified_at=T1,
        verified_by="aeat-import",
        filed_at=T1,
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
        filed_at=T1,
        filed_by="aeat-import",
        notes=None,
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUSTM303ABC123",
            imported_at=T1,
        ),
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), baseline_filing))

    return work_unit, revision, baseline_filing


def seed_local_filing_record(
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


@dataclass(frozen=True, slots=True)
class AmendOutcome:
    """Bundle returned by drive_amend_creates_complementaria.

    Holds every state slice the focused tests inspect:
    work_unit + baseline + baseline_revision + the new filing
    record produced by ``amend_modelo_revision``.
    """

    work_unit: WorkUnit
    baseline_revision: CalculationRevision
    baseline: ModeloRecord
    new_filing: ModeloRecord


def seed_engine_computed_baseline(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> tuple[WorkUnit, CalculationRevision, ModeloRecord]:
    """Seed a confirmed 130 baseline whose values the real engine computed from its inputs."""
    _wu_repo, _cr_repo, _fr_repo, _evidence_repo, _bv_repo = repos
    work_unit = seed_work_unit(_wu_repo, operation=operation)
    snapshot = operation.snapshot("130", filing_year=YEAR, period="1T")
    engine_inputs = {
        AMEND_INCOME_CASILLA: Decimal("1000"),
        AMEND_WITHHELD_CASILLA: Decimal("0"),
        AMEND_PREVIOUS_PAYMENT_CASILLA: Decimal("0"),
        AMEND_HOME_DEDUCTION_CASILLA: Decimal("0"),
        AMEND_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        validated_casilla_id("gastos-deducibles-previos"): Decimal("0"),
        validated_casilla_id("rendimiento-neto-reducible-art-32-1"): Decimal("0"),
    }
    engine_bindings = {
        "modelo-130-actividad-economica-ingresos-cumulative": Decimal("1000"),
        "modelo-130-actividad-economica-gastos-cumulative": Decimal("0"),
        "modelo-130-volumen-ingresos-agrario": Decimal("0"),
        "modelo-130-retenciones-agrarias": Decimal("0"),
        "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    }
    enum_bindings = {"modelo-130-estimacion-directa-modalidad": "directa_simplificada"}
    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=engine_inputs,
        binding_values=engine_bindings,
        enum_binding_values=enum_bindings,
        date_context={},
    )
    input_strings = {key: str(value) for key, value in engine_inputs.items()}
    binding_strings = {key: str(value) for key, value in engine_bindings.items()} | enum_bindings
    baseline_layer = CalculationOperatorLayer(decimal_casilla_inputs=input_strings, binding_overrides=binding_strings)
    _, baseline_revision, baseline = seed_external_baseline(
        repos,
        casilla_values=engine_result.values,
        input_values_by_casilla_id=input_strings,
        binding_overrides=binding_strings,
        observations=engine_result.observations,
        operator_layer=baseline_layer,
        operation=operation,
    )
    return work_unit, baseline_revision, baseline


def drive_amend_creates_complementaria(repos: Repos, *, operation: PinnedAuthorityOperation) -> AmendOutcome:
    """Run the seed-baseline + amend scenario and bundle the observable state."""
    work_unit, baseline_revision, baseline = seed_engine_computed_baseline(repos, operation=operation)
    with bundled_indexed_authority().operation() as operation:
        new_filing = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="under-reported turnover discovered in audit",
            actor="operator-A",
            clock=T4,
        )
    return AmendOutcome(
        work_unit=work_unit,
        baseline_revision=baseline_revision,
        baseline=baseline,
        new_filing=new_filing,
    )
