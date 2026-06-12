"""Shared support for modelo file-flow application tests."""


from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.config import Settings
from ....core.resources import resources
from ....domain.buckets import (
    BucketEventHistoryRepository,
)
from ....domain.buckets import (
    BucketEventObjectType as BucketEventObjectType,
)
from ....domain.buckets import (
    BucketEventType as BucketEventType,
)
from ....domain.calculations.registry import (
    CasillaObservation,
    InputKind,
    RegistryModeloObservation,
    previous_filing_observation_requirements,
    relation_source_requirements,
)
from ....domain.deadlines import DeadlineEngine, IVARegime, TaxpayerProfile
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos._filing_record import ExternalEvidenceKind, ModeloRecord, ModeloRecordStatus
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ....domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
)
from ....domain.modelos._work_unit import WorkUnit
from ....domain.submission import SubmissionEngine
from ....domain.transactions import TransactionCatalogue
from ....tests.secure_sql import isolated_runtime_profile
from ...auth import AuthProviderDescription, AuthProviderKind
from ...calculations import CalculationObservationRepository
from ...filing import (
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    filing_profile_from_taxpayer,
)
from ...workflow import (
    DeadlineEngineAdapter,
    ModeloInputs,
    WorkflowAbortReason,
    WorkflowEngine,
    WorkflowPurpose,
    WorkflowStage,
)
from .. import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    ModeloWorkflowGateError,
    VerificationReportNotFoundError,
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    get_calculation_revision,
    get_filing_record,
    get_verification_report,
    get_work_unit,
    import_external_filing_evidence,
    list_calculation_revisions,
    list_filing_records,
    list_verification_reports,
    mark_revision_verificado_completo,
    verify_modelo_revision,
)
from .._actions import workflow_period_for_work_unit
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = [
    "BucketEventObjectType",
    "BucketEventType",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionState",
    "CalculationRevisionStateError",
    "ModeloRecordNotFoundError",
    "ModeloRecordStatus",
    "ModeloVerificationFindingKind",
    "ModeloVerificationFindingSeverity",
    "ModeloWorkflowGateError",
    "VerificationCompletenessStatus",
    "VerificationReportNotFoundError",
    "WorkflowAbortReason",
    "WorkflowPurpose",
    "WorkflowStage",
    "asyncio",
    "calculate_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "list_calculation_revisions",
    "list_filing_records",
    "list_verification_reports",
    "mark_revision_verificado_completo",
    "upsert_work_unit",
]


_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 14, 14, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 15, 15, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_T5 = datetime(2026, 4, 17, 13, 0, 0, tzinfo=UTC)

_VERIFY_MODELO = "180"
_VERIFY_REVISION = "2023-y-siguientes"
_VERIFY_PERIOD = "0A"
_VERIFY_YEAR = 2024


def _registry_required_manual_casillas() -> tuple[str, ...]:
    """Return the required ``input_kind=manual`` casilla ids the verifier
    will demand for modelo 180 / 2024 / period 0A. Reads the real
    registry — no duplication of revision data in the test."""

    snapshot = resources().modelos.authority.snapshot(_VERIFY_MODELO, filing_year=_VERIFY_YEAR, period=_VERIFY_PERIOD)
    return tuple(str(c.id) for c in snapshot.revision.casillas if c.required and c.input_kind == InputKind.MANUAL)


def _registry_required_manual_casillas_for(*, modelo: str, filing_year: int, period: str) -> tuple[str, ...]:
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)
    return tuple(str(c.id) for c in snapshot.revision.casillas if c.required and c.input_kind == InputKind.MANUAL)


_DEFAULT_180_RELATION_VALUES: dict[str, Decimal] = {
    "modelo-180-rel-115-perceptores-anual": Decimal("0"),
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


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Yield the five catalogue repositories over an encrypted SQLite
    database through the shared active-profile runtime. Tuple shape:
    ``(work_unit, calculation_revision, filing_record,
    verification_report, bucket_event_history)``."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default") as profile:
        objects = profile.repository
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        fr = ModeloRecordCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, fr, vr, bv


def _seed_work_unit(
    wu_repo: WorkUnitCatalogueRepository,
    *,
    bucket_id: str = "default",
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
_DEFAULT_130_BASELINE_INPUTS: dict[str, Decimal] = {
    "01": Decimal("10000"),  # economic-activity gross income
    "02": Decimal("3000"),  # economic-activity gross expenses
    "05": Decimal("0"),
    "06": Decimal("0"),
    "08": Decimal("0"),
    "10": Decimal("0"),
    "15": Decimal("0"),
    "16": Decimal("0"),
    "18": Decimal("0"),
}


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _cross_period_source_groups(work_unit: WorkUnit) -> dict[tuple[str, int, str], set[str]]:
    snapshot = resources().modelos.authority.snapshot(
        work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    groups: dict[tuple[str, int, str], set[str]] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ):
        groups.setdefault(
            (requirement.modelo, requirement.filing_year, requirement.period),
            set(),
        ).update(requirement.source_casillas)
    for requirement in relation_source_requirements(
        snapshot.revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ):
        for period in requirement.periods:
            groups.setdefault(
                (requirement.source_modelo, requirement.filing_year, period),
                set(),
            ).add(requirement.source_output)
    return groups


def _source_casilla_values(source_casillas: set[str]) -> dict[str, Decimal]:
    return {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(sorted(source_casillas))}


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
    for (source_modelo, filing_year, period), source_casillas in sorted(groups.items()):
        source_period = Period.from_year_and_code(filing_year, period)
        values = _source_casilla_values(source_casillas)
        current = filing_catalogue.current_for(
            bucket_id=work_unit.bucket_id,
            modelo=source_modelo,
            filing_year=filing_year,
            period=source_period,
        )
        if current is None:
            source_snapshot = resources().modelos.authority.snapshot(
                source_modelo,
                filing_year=filing_year,
                period=period,
            )
            evidence_reference_id = f"JUST-{source_modelo}-{filing_year}-{period}"
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
                revision_id=source_snapshot.revision.id,
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
        observation_repository.save_observation(
            RegistryModeloObservation(
                modelo=source_modelo,
                filing_year=filing_year,
                period=period,
                observations=tuple(
                    CasillaObservation(casilla_id=casilla_id, value=value) for casilla_id, value in values.items()
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_T0,
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


class _RevisionInputsProvider:
    def __init__(self, *, revision: CalculationRevision, work_unit: WorkUnit) -> None:
        self._revision = revision
        self._modelo = work_unit.modelo
        self._period = _canonical_work_unit_period(work_unit)

    def load_inputs(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
    ) -> ModeloInputs:
        del profile
        assert modelo == self._modelo
        assert period == self._period
        return {
            **dict(self._revision.inputs_snapshot),
            **dict(self._revision.binding_overrides),
        }


class _RevisionDraftBuilder:
    def __init__(self, *, work_unit: WorkUnit, actor: str, clock: datetime) -> None:
        self._work_unit = work_unit
        self._actor = actor
        self._clock = clock
        self._schema_provider = build_runtime_schema_provider(
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            modelos=(work_unit.modelo,),
        )

    def build(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
        inputs: ModeloInputs,
        fail_on_warning: bool = False,
    ):
        draft = build_draft(
            modelo=modelo,
            period=period,
            profile=filing_profile_from_taxpayer(profile),
            inputs=inputs,
            schema_provider=self._schema_provider,
            fail_on_warning=fail_on_warning,
        )
        return approve_draft(
            draft,
            bucket_id=self._work_unit.bucket_id,
            approved_by=self._actor,
            schema_provider=self._schema_provider,
            transaction_catalogue=TransactionCatalogue(),
            approved_at=self._clock,
        )


class _DeadlineWindowChecker:
    def __init__(self, *, profile: TaxpayerProfile, engine: DeadlineEngine) -> None:
        self._profile = profile
        self._engine = engine

    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        schedule = self._engine.compute(self._profile, period.year, today=today)
        return any(
            obligation.modelo == modelo
            and obligation.period == period
            and obligation.opens_on <= today <= obligation.closes_on
            for obligation in schedule.obligations
        )


@dataclass
class _AuthProvider:
    available: bool = True
    kind: AuthProviderKind = AuthProviderKind.CERTIFICATE
    describe_calls: int = 0

    def describe(self) -> AuthProviderDescription:
        self.describe_calls += 1
        return AuthProviderDescription(
            kind=self.kind,
            label="Workflow test certificate",
            configured=True,
            available=self.available,
            identity_nif="X1234567L",
            subject="CN=Workflow Test",
            expires_on=date(2027, 1, 15),
            health_severity="OK" if self.available else "ERROR",
        )


@dataclass
class _WorkflowGate:
    engine: WorkflowEngine
    profile: TaxpayerProfile
    auth_provider: _AuthProvider = field(default_factory=_AuthProvider)


def _workflow_gate(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    clock: datetime,
    auth_provider: _AuthProvider | None = None,
) -> _WorkflowGate:
    profile = _workflow_profile()
    deadline_engine = DeadlineEngine()
    provider = auth_provider or _AuthProvider()
    submission_engine = SubmissionEngine(
        auth_provider=provider,
        deadline_checker=_DeadlineWindowChecker(profile=profile, engine=deadline_engine),
        settings=Settings(),
    )
    return _WorkflowGate(
        profile=profile,
        auth_provider=provider,
        engine=WorkflowEngine(
            deadline_engine=DeadlineEngineAdapter(deadline_engine),
            filing_draft_builder=_RevisionDraftBuilder(  # pyrefly: ignore[bad-argument-type]  # reason: _RevisionDraftBuilder is a duck-typed test fake whose .build() returns ModeloDraft which structurally satisfies RegistryModeloDraftProtocol at runtime
                work_unit=work_unit,
                actor="operator-A",
                clock=clock,
            ),
            submission_engine=submission_engine,
            session=None,
            certificate_bundle=None,
            inputs_provider=_RevisionInputsProvider(revision=revision, work_unit=work_unit),
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
    auth_provider: _AuthProvider | None = None,
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
        auth_provider=auth_provider,
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
    auth_provider: _AuthProvider | None = None,
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
        auth_provider=auth_provider,
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
        bucket_id="default",
        modelo=_VERIFY_MODELO,
        filing_year=_VERIFY_YEAR,
        period=Period.from_year_and_code(_VERIFY_YEAR, _VERIFY_PERIOD),
        revision_id=_VERIFY_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
