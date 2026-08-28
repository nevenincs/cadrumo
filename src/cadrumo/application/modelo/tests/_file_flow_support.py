"""Shared support for modelo file-flow application tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.config import Settings
from ....domain.buckets import (
    BucketEventObjectType as BucketEventObjectType,
)
from ....domain.buckets import (
    BucketEventType as BucketEventType,
)
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ....domain.calculations.registry.relations import relation_source_requirements
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.temporal import select_revision
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    WorkUnit,
    upsert_work_unit,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.registry_tree import bundled_registry_tree
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from ...workflow.abort import WorkflowAbortReason
from ...workflow.engine import WorkflowEngine
from ...workflow.run_models import WorkflowPurpose, WorkflowStage
from .._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    ModeloWorkflowGateError,
    VerificationReportNotFoundError,
)
from .._calculation_actions import (
    calculate_modelo_revision,
    get_calculation_revision,
    list_calculation_revisions,
    mark_revision_verificado_completo,
)
from .._filing_actions import (
    file_modelo_revision,
    get_filing_record,
    get_verification_report,
    list_filing_records,
    list_verification_reports,
)
from .._verification_actions import verify_modelo_revision
from .._work_lifecycle import (
    create_work_unit,
    get_work_unit,
)
from .._workflow_gate import build_revision_workflow_engine, workflow_period_for_work_unit
from ..external_import_actions import import_external_filing_evidence
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = [
    "DEFAULT_130_BASELINE_INPUTS",
    "DEFAULT_130_BINDING_VALUES",
    "DEFAULT_180_BINDING_VALUES",
    "DEFAULT_180_RELATION_VALUES",
    "M111_ACTIVITY_AMOUNT_CASILLA",
    "M111_ACTIVITY_COUNT_CASILLA",
    "M111_ACTIVITY_WITHHELD_CASILLA",
    "M111_EMPLOYMENT_WITHHELD_CASILLA",
    "M111_FORESTRY_WITHHELD_CASILLA",
    "M111_IMAGE_RIGHTS_WITHHELD_CASILLA",
    "M111_IMPUTED_INCOME_WITHHELD_CASILLA",
    "M111_PRIZE_WITHHELD_CASILLA",
    "M111_PROFESSIONAL_WITHHELD_CASILLA",
    "M111_TOTAL_WITHHELD_CASILLA",
    "M130_AGRARIAN_VOLUME_CASILLA",
    "M130_AGRARIAN_WITHHELD_CASILLA",
    "M130_CARRY_FORWARD_CASILLA",
    "M130_EXPENSE_CASILLA",
    "M130_HOME_DEDUCTION_CASILLA",
    "M130_INCOME_CASILLA",
    "M130_NET_RESULT_CASILLA",
    "M130_PRIOR_RETURN_RESULT_CASILLA",
    "M130_SALDO_NEGATIVO_CASILLA",
    "M130_WITHHELD_CASILLA",
    "M180_PERCEPTOR_BASE_CASILLA",
    "T0",
    "T1",
    "T2",
    "T3",
    "T4",
    "T5",
    "VERIFY_MODELO",
    "VERIFY_PERIOD",
    "VERIFY_REVISION",
    "VERIFY_YEAR",
    "BucketEventObjectType",
    "BucketEventType",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionState",
    "CalculationRevisionStateError",
    "Decimal",
    "FileFlowRuntime",
    "ModeloRecordNotFoundError",
    "ModeloRecordStatus",
    "ModeloVerificationFindingKind",
    "ModeloVerificationFindingSeverity",
    "ModeloWorkflowGateError",
    "Repos",
    "VerificationCompletenessStatus",
    "VerificationReportNotFoundError",
    "WorkflowAbortReason",
    "WorkflowGate",
    "WorkflowPurpose",
    "WorkflowStage",
    "asyncio",
    "calculate_modelo_revision",
    "canonical_work_unit_period",
    "create_work_unit",
    "file_modelo_revision",
    "file_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "list_calculation_revisions",
    "list_filing_records",
    "list_verification_reports",
    "mark_revision_verificado_completo",
    "registry_required_manual_casillas",
    "registry_required_manual_casillas_for",
    "seed_clean_cross_period_sources",
    "seed_modelo_180_work_unit",
    "seed_work_unit",
    "target_filing_records",
    "upsert_work_unit",
    "verify_modelo_revision",
    "verify_revision",
    "workflow_gate",
    "workflow_profile",
]


_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 14, 14, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 15, 15, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_T5 = datetime(2026, 4, 17, 13, 0, 0, tzinfo=UTC)
_FILE_FLOW_PROFILE_ID = "11111111-1111-4111-8111-111111111111"

_VERIFY_MODELO = "180"
_VERIFY_REVISION = "2023-y-siguientes"
_VERIFY_PERIOD = "0A"
_VERIFY_YEAR = 2024
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
    UserProfileFact(path="censo.activity_start_date", value=date(2000, 1, 1)),
    # Modelo 111 refuses a defaulted colegio-concertado declaration: the fichero
    # carries the row as filer data, so it must be stated rather than assumed.
    # False is the truthful value for this natural-person filer.
    UserProfileFact(path="withholding.colegio_concertado", value=False),
)


def _resolved_revision(*, modelo: str, filing_year: int, period: str) -> ModeloRevision:
    """Resolve a law-determined revision without touching the tree-wide authority.

    ``load_registry_tree`` compiles the tree without validating it, and
    ``select_revision`` is a pure function with no validation of its own -- this
    works for any modelo, layout-bearing or not, unlike
    ``bundled_authority()``, whose ``.load()`` validates the entire
    registry tree and currently refuses unconditionally as a result.
    """
    modelos, _catalogues = bundled_registry_tree()
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    return select_revision(modelo_definition, filing_year=filing_year, period=period)


def _registry_required_manual_casillas() -> tuple[CasillaId, ...]:
    """Return required numeric manual casillas for M180 calculate-input fixtures.

    Modelo 180 also declares required row/detail text fields. Those do not belong
    on the numeric ``casilla_inputs`` channel; feeding them there correctly raises
    before verification.
    """

    revision = _resolved_revision(modelo=_VERIFY_MODELO, filing_year=_VERIFY_YEAR, period=_VERIFY_PERIOD)
    return tuple(
        c.id for c in revision.casillas if c.required and c.input_kind == InputKind.MANUAL and c.data_type == "money"
    )


def _registry_required_manual_casillas_for(*, modelo: str, filing_year: int, period: str) -> tuple[CasillaId, ...]:
    revision = _resolved_revision(modelo=modelo, filing_year=filing_year, period=period)
    return tuple(c.id for c in revision.casillas if c.required and c.input_kind == InputKind.MANUAL)


_DEFAULT_180_RELATION_VALUES: dict[str, Decimal] = {
    "modelo-180-rel-115-base-anual": Decimal("0"),
    "modelo-180-rel-115-retenciones-anual": Decimal("0"),
}
_DEFAULT_180_BINDING_VALUES: dict[str, Decimal] = {
    "modelo-180-115-perceptores-anual": Decimal("0"),
    "modelo-180-115-base-anual": Decimal("0"),
    "modelo-180-115-retenciones-anual": Decimal("0"),
}


_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]


def _repos(tmp_path: Path) -> Iterator[_Repos]:
    """Yield the five catalogue repositories over an encrypted SQLite
    database through the shared active-profile runtime. Tuple shape:
    ``(work_unit, calculation_revision, filing_record,
    verification_report, bucket_event_history)``."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FILE_FLOW_PROFILE_ID) as profile:
        objects = profile.repository
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        fr = ModeloRecordCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, fr, vr, bv


@dataclass(frozen=True, slots=True)
class _FileFlowRuntime:
    """The live engine plus the repository bundle sharing it.

    Exposes the engine the repositories already use so a test can observe how
    many SQL transactions a composed write spans, which is the only way to tell
    a single unit of work from a sequence of independent saves.
    """

    engine: Engine
    repos: _Repos


def _file_flow_runtime(tmp_path: Path) -> Iterator[_FileFlowRuntime]:
    """Yield the file-flow repository bundle alongside its live engine."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FILE_FLOW_PROFILE_ID) as profile:
        objects = profile.repository
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        yield _FileFlowRuntime(
            engine=objects.engine,
            repos=(
                WorkUnitCatalogueRepository(objects=objects),
                CalculationRevisionCatalogueRepository(objects=objects),
                ModeloRecordCatalogueRepository(objects=objects),
                VerificationReportCatalogueRepository(objects=objects),
                BucketEventHistoryRepository(objects=objects),
            ),
        )


def _seed_work_unit(
    wu_repo: WorkUnitCatalogueRepository,
    *,
    bucket_id: str = _FILE_FLOW_PROFILE_ID,
    modelo: str = "130",
    filing_year: int = 2026,
    period: str = "1T",
    revision_id: str = "2019-y-siguientes",
):
    """Default fixture: modelo 130 1T 2026 — autónomo IRPF quarterly,
    9 manual casillas + 10 formulas + 1 prior-filing binding.
    Registry-resolvable so the formula engine runs end-to-end."""

    return create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision_id=revision_id,
        repository=wu_repo,
        clock=_T0,
    )


_DEFAULT_130_BINDING_VALUES = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
}


_M130_INCOME_CASILLA: CasillaId = validated_casilla_id("01")
_M130_EXPENSE_CASILLA: CasillaId = validated_casilla_id("02")
_M130_NET_RESULT_CASILLA: CasillaId = validated_casilla_id("03")
_M130_PREVIOUS_PAYMENTS_CASILLA: CasillaId = validated_casilla_id("05")
_M130_WITHHELD_CASILLA: CasillaId = validated_casilla_id("06")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_M130_CARRY_FORWARD_CASILLA: CasillaId = validated_casilla_id("15")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")
_M111_EMPLOYMENT_WITHHELD_CASILLA: CasillaId = validated_casilla_id("03")
_M111_PROFESSIONAL_WITHHELD_CASILLA: CasillaId = validated_casilla_id("06")
_M111_PRIZE_WITHHELD_CASILLA: CasillaId = validated_casilla_id("09")
_M111_IMAGE_RIGHTS_WITHHELD_CASILLA: CasillaId = validated_casilla_id("12")
_M111_FORESTRY_WITHHELD_CASILLA: CasillaId = validated_casilla_id("15")
_M111_IMPUTED_INCOME_WITHHELD_CASILLA: CasillaId = validated_casilla_id("18")
_M111_ACTIVITY_COUNT_CASILLA: CasillaId = validated_casilla_id("21")
_M111_ACTIVITY_AMOUNT_CASILLA: CasillaId = validated_casilla_id("24")
_M111_ACTIVITY_WITHHELD_CASILLA: CasillaId = validated_casilla_id("27")
_M111_TOTAL_WITHHELD_CASILLA: CasillaId = validated_casilla_id("29")
_M180_PERCEPTOR_BASE_CASILLA: CasillaId = validated_casilla_id("perc.base")

_DEFAULT_130_BASELINE_INPUTS: dict[CasillaId, Decimal] = {
    _M130_INCOME_CASILLA: Decimal("10000"),  # economic-activity gross income
    _M130_EXPENSE_CASILLA: Decimal("3000"),  # economic-activity gross expenses
    _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
    _M130_WITHHELD_CASILLA: Decimal("0"),
    _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
    _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        activity_start_date=date(2000, 1, 1),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _cross_period_source_groups(work_unit: WorkUnit) -> dict[tuple[str, int, str], set[CasillaId]]:
    revision = _resolved_revision(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    groups: dict[tuple[str, int, str], set[CasillaId]] = {}
    for requirement in previous_filing_observation_requirements(
        revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ):
        groups.setdefault(
            (requirement.source_modelo, requirement.filing_year, requirement.periods[0]),
            set(),
        ).update(requirement.source_casilla_ids)
    for requirement in relation_source_requirements(
        revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ):
        for period in requirement.periods:
            groups.setdefault(
                (requirement.source_modelo, requirement.filing_year, period),
                set(),
            ).update(requirement.source_casilla_ids)
    return groups


def _source_casilla_values(source_casilla_ids: set[CasillaId]) -> dict[CasillaId, Decimal]:
    return {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(sorted(source_casilla_ids))}


def _seed_clean_cross_period_sources(
    work_unit: WorkUnit,
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
) -> None:
    groups = _cross_period_source_groups(work_unit)
    if not groups:
        return
    observation_repository = CalculationObservationRepository()
    filing_catalogue = filing_repository.load()
    for (source_modelo, filing_year, period), source_casilla_ids in sorted(groups.items()):
        source_period = Period.from_year_and_code(filing_year, period)
        source_revision = _resolved_revision(modelo=source_modelo, filing_year=filing_year, period=period)
        values = _source_casilla_values(source_casilla_ids)
        current = filing_catalogue.current_for(
            bucket_id=work_unit.bucket_id,
            modelo=source_modelo,
            filing_year=filing_year,
            period=source_period,
        )
        evidence_reference_id = f"CSV{source_modelo}{filing_year}{period}".upper()
        if current is None:
            persist_justificante_metadata(
                evidence_reference_id,
                modelo=source_modelo,
                filing_year=filing_year,
                period=period,
                captured_at=_T0,
            )
            source_work_unit = create_work_unit(
                bucket_id=work_unit.bucket_id,
                modelo=source_modelo,
                filing_year=filing_year,
                period=source_period,
                revision_id=source_revision.id,
                repository=work_unit_repository,
                clock=_T0,
            )
            import_external_filing_evidence(
                work_unit_id=source_work_unit.work_unit_id,
                casilla_values=values,
                evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                evidence_reference_id=evidence_reference_id,
                actor="aeat-import-test",
                work_unit_repository=work_unit_repository,
                calculation_repository=calculation_repository,
                filing_repository=filing_repository,
                bucket_event_repository=bucket_event_repository,
                expected_tax_id="X1234567L",
                clock=_T0,
            )
            filing_catalogue = filing_repository.load()
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo=source_modelo,
                    filing_year=filing_year,
                    period=period,
                    observations=registry_grounded_observations(
                        modelo=source_modelo,
                        filing_year=filing_year,
                        period=period,
                        casilla_values=values,
                    ),
                ),
                source_kind="aeat_sede_justificante",
                captured_at=_T0,
                stamped_revision_id=source_revision.id,
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": f"EXP-{source_modelo}-{filing_year}-{period}",
                    "aeat_justificante_csv": evidence_reference_id,
                    "authenticated_identity": "X1234567L",
                },
            )
        )


def seed_clean_cross_period_sources(
    work_unit: WorkUnit,
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
) -> None:
    _seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        bucket_event_repository=bucket_event_repository,
    )


def _target_filing_records(
    records: tuple[object, ...],
    work_unit: WorkUnit,
) -> tuple[ModeloRecord, ...]:
    result: list[ModeloRecord] = []
    for record in records:
        if isinstance(record, ModeloRecord) and record.work_unit_id == work_unit.work_unit_id:
            result.append(record)
    return tuple(result)


def _canonical_work_unit_period(work_unit: WorkUnit) -> Period:
    return workflow_period_for_work_unit(work_unit)


@dataclass
class _WorkflowGate:
    engine: WorkflowEngine
    profile: TaxpayerProfile


def _workflow_gate(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    clock: datetime,
) -> _WorkflowGate:
    profile = _workflow_profile()
    return _WorkflowGate(
        profile=profile,
        engine=build_revision_workflow_engine(
            revision=revision,
            work_unit=work_unit,
            profile=profile,
            actor="operator-A",
            clock=clock,
            settings=Settings(),
        ),
    )


def _file_revision(
    calculation_revision_id: str,
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    actor: str = "operator-A",
    notes: str | None = None,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    clock: datetime,
):
    _seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        bucket_event_repository=bucket_event_repository,
    )
    gate = _workflow_gate(
        revision=revision,
        work_unit=work_unit,
        clock=clock,
    )
    return file_modelo_revision(
        calculation_revision_id,
        actor=actor,
        workflow_profile=gate.profile,
        notes=notes,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        bucket_event_repository=bucket_event_repository,
        workflow_engine=gate.engine,
        clock=clock,
    )


def _verify_revision(
    calculation_revision_id: str,
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    actor: str = "operator-A",
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    verification_repository: VerificationReportCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
    clock: datetime,
):
    _seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository or ModeloRecordCatalogueRepository(),
        bucket_event_repository=bucket_event_repository,
    )
    gate = _workflow_gate(
        revision=revision,
        work_unit=work_unit,
        clock=clock,
    )
    return verify_modelo_revision(
        calculation_revision_id,
        actor=actor,
        workflow_profile=gate.profile,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        bucket_event_repository=bucket_event_repository,
        workflow_engine=gate.engine,
        clock=clock,
    )


def _seed_modelo_180_work_unit(wu_repo: WorkUnitCatalogueRepository):
    return create_work_unit(
        bucket_id=_FILE_FLOW_PROFILE_ID,
        modelo=_VERIFY_MODELO,
        filing_year=_VERIFY_YEAR,
        period=Period.from_year_and_code(_VERIFY_YEAR, _VERIFY_PERIOD),
        revision_id=_VERIFY_REVISION,
        repository=wu_repo,
        clock=_T0,
    )


DEFAULT_130_BASELINE_INPUTS = _DEFAULT_130_BASELINE_INPUTS
DEFAULT_130_BINDING_VALUES = _DEFAULT_130_BINDING_VALUES
DEFAULT_180_BINDING_VALUES = _DEFAULT_180_BINDING_VALUES
DEFAULT_180_RELATION_VALUES = _DEFAULT_180_RELATION_VALUES
M111_ACTIVITY_AMOUNT_CASILLA = _M111_ACTIVITY_AMOUNT_CASILLA
M111_ACTIVITY_COUNT_CASILLA = _M111_ACTIVITY_COUNT_CASILLA
M111_ACTIVITY_WITHHELD_CASILLA = _M111_ACTIVITY_WITHHELD_CASILLA
M111_EMPLOYMENT_WITHHELD_CASILLA = _M111_EMPLOYMENT_WITHHELD_CASILLA
M111_FORESTRY_WITHHELD_CASILLA = _M111_FORESTRY_WITHHELD_CASILLA
M111_IMAGE_RIGHTS_WITHHELD_CASILLA = _M111_IMAGE_RIGHTS_WITHHELD_CASILLA
M111_IMPUTED_INCOME_WITHHELD_CASILLA = _M111_IMPUTED_INCOME_WITHHELD_CASILLA
M111_PRIZE_WITHHELD_CASILLA = _M111_PRIZE_WITHHELD_CASILLA
M111_PROFESSIONAL_WITHHELD_CASILLA = _M111_PROFESSIONAL_WITHHELD_CASILLA
M111_TOTAL_WITHHELD_CASILLA = _M111_TOTAL_WITHHELD_CASILLA
M130_AGRARIAN_VOLUME_CASILLA = _M130_AGRARIAN_VOLUME_CASILLA
M130_AGRARIAN_WITHHELD_CASILLA = _M130_AGRARIAN_WITHHELD_CASILLA
M130_CARRY_FORWARD_CASILLA = _M130_CARRY_FORWARD_CASILLA
M130_EXPENSE_CASILLA = _M130_EXPENSE_CASILLA
M130_HOME_DEDUCTION_CASILLA = _M130_HOME_DEDUCTION_CASILLA
M130_INCOME_CASILLA = _M130_INCOME_CASILLA
M130_NET_RESULT_CASILLA = _M130_NET_RESULT_CASILLA
M130_PRIOR_RETURN_RESULT_CASILLA = _M130_PRIOR_RETURN_RESULT_CASILLA
M130_SALDO_NEGATIVO_CASILLA = _M130_SALDO_NEGATIVO_CASILLA
M130_WITHHELD_CASILLA = _M130_WITHHELD_CASILLA
M180_PERCEPTOR_BASE_CASILLA = _M180_PERCEPTOR_BASE_CASILLA
Repos = _Repos
T0 = _T0
T1 = _T1
T2 = _T2
T3 = _T3
T4 = _T4
T5 = _T5
VERIFY_MODELO = _VERIFY_MODELO
VERIFY_PERIOD = _VERIFY_PERIOD
VERIFY_REVISION = _VERIFY_REVISION
VERIFY_YEAR = _VERIFY_YEAR
WorkflowGate = _WorkflowGate
canonical_work_unit_period = _canonical_work_unit_period
file_revision = _file_revision
registry_required_manual_casillas = _registry_required_manual_casillas
registry_required_manual_casillas_for = _registry_required_manual_casillas_for
seed_modelo_180_work_unit = _seed_modelo_180_work_unit
seed_work_unit = _seed_work_unit
target_filing_records = _target_filing_records
verify_revision = _verify_revision
workflow_gate = _workflow_gate
workflow_profile = _workflow_profile
FileFlowRuntime = _FileFlowRuntime
