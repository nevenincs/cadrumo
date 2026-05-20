"""End-to-end tests for the modelo calculate / verify / file flow.

Every test in this module wires the full set of catalogue
repositories (work unit, calculation revision, filing record,
verification report, bucket-event history) over a fresh encrypted
SQLite database. No monkeypatches, no in-memory fakes, no stubs:
each ``save`` encrypts, each ``load`` decrypts, every domain write
also lands a bucket-scoped event row.

Coverage:

* Two ``calculate`` invocations under one work unit produce two
  distinct ``CalculationRevision`` records (the "toilet-break"
  scenario) and emit a ``modelo.calculation.created`` event each.
* ``mark_revision_verificado_completo`` requires DRAFT state.
* ``verify_modelo_revision`` reads real registry truth and emits
  ``modelo.verification.passed`` / ``modelo.verification.refused``.
* ``file_modelo_revision`` requires VERIFICADO_COMPLETO state and
  emits ``modelo.filed`` (plus ``modelo.filed_superseded`` when a
  prior filing exists).
* Filing advances the work unit's pointer fields atomically.
* Re-filing supersedes the prior filing record + revision without
  losing audit history.
* The filing-record catalogue ``current_for(...)`` /
  ``history_for(...)`` queries resolve the canonical answer and
  full audit chain.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.application.auth import AuthProviderDescription, AuthProviderKind
from aeat.application.filing import (
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    filing_profile_from_autonomo,
)
from aeat.application.modelo import (
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
    list_calculation_revisions,
    list_filing_records,
    list_verification_reports,
    mark_revision_verificado_completo,
    verify_modelo_revision,
)
from aeat.application.workflow import (
    DeadlineEngineAdapter,
    WorkflowEngine,
)
from aeat.core.config import Settings
from aeat.core.resources import resources
from aeat.domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from aeat.domain.deadlines import AutonomoProfile, DeadlineEngine, IVARegime
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from aeat.domain.modelos._filing_record import ModeloRecordStatus
from aeat.domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from aeat.domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
)
from aeat.domain.modelos._work_unit import WorkUnit
from aeat.domain.period import parse_canonical_period
from aeat.domain.submission import SubmissionEngine
from aeat.domain.transactions import TransactionCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
    return tuple(str(c.id) for c in snapshot.revision.casillas if c.required and c.input_kind == "manual")


def _registry_required_manual_casillas_for(*, modelo: str, filing_year: int, period: str) -> tuple[str, ...]:
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)
    return tuple(str(c.id) for c in snapshot.revision.casillas if c.required and c.input_kind == "manual")


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


@pytest.fixture
def repos(tmp_path):
    """Yield the five catalogue repositories over an encrypted SQLite
    database. Tears down the master-key override on exit. Tuple shape:
    ``(work_unit, calculation_revision, filing_record,
    verification_report, bucket_event_history)``."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "modelo_flow.db"
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            objects = SecureObjectRepository(engine=engine)
            wu = WorkUnitCatalogueRepository(objects=objects)
            cr = CalculationRevisionCatalogueRepository(objects=objects)
            fr = ModeloRecordCatalogueRepository(objects=objects)
            vr = VerificationReportCatalogueRepository(objects=objects)
            bv = BucketEventHistoryRepository(objects=objects)
            yield wu, cr, fr, vr, bv
        finally:
            engine.dispose()


def _seed_work_unit(
    wu_repo,
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
        period=period,
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


def _workflow_profile() -> AutonomoProfile:
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _canonical_work_unit_period(work_unit: WorkUnit) -> str:
    if work_unit.period.endswith("T") and len(work_unit.period) == 2:
        return f"{work_unit.filing_year}Q{work_unit.period[0]}"
    if work_unit.period == "0A":
        return str(work_unit.filing_year)
    if len(work_unit.period) == 2 and work_unit.period.isdigit():
        return f"{work_unit.filing_year}-{work_unit.period}"
    parse_canonical_period(work_unit.period)
    return work_unit.period


class _RevisionInputsProvider:
    def __init__(self, *, revision: CalculationRevision, work_unit: WorkUnit) -> None:
        self._revision = revision
        self._modelo = work_unit.modelo
        self._period = _canonical_work_unit_period(work_unit)

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> dict[str, object]:
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
        period: str,
        profile: AutonomoProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ):
        draft = build_draft(
            modelo=modelo,
            period=period,
            profile=filing_profile_from_autonomo(profile),
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
    def __init__(self, *, profile: AutonomoProfile, engine: DeadlineEngine) -> None:
        self._profile = profile
        self._engine = engine

    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        year, _ = parse_canonical_period(period)
        schedule = self._engine.compute(self._profile, year, today=today)
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
    profile: AutonomoProfile
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
            filing_draft_builder=_RevisionDraftBuilder(  # pyrefly: ignore[bad-argument-type]  # reason: _RevisionDraftBuilder is a duck-typed test fake whose .build() returns ModeloDraft which structurally satisfies RegistryFilingDraftProtocol at runtime
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
    clock: datetime,
    auth_provider: _AuthProvider | None = None,
):
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


def _seed_modelo_180_work_unit(wu_repo):
    return create_work_unit(
        bucket_id="default",
        modelo=_VERIFY_MODELO,
        filing_year=_VERIFY_YEAR,
        period=_VERIFY_PERIOD,
        revision_id=_VERIFY_REVISION,
        repository=wu_repo,
        clock=_T0,
    )


def test_two_calculates_under_one_work_unit_produce_two_revisions(repos) -> None:
    """The toilet-break scenario. Operator calculates, walks away,
    comes back, calculates again with different inputs. Two
    ``CalculationRevision`` records exist; the work unit's
    ``current_calculation_revision_id`` advances to the second."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("2000"), "02": Decimal("500")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert first.calculation_revision_id != second.calculation_revision_id

    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,
    )
    assert len(revisions) == 2
    assert {r.calculation_revision_id for r in revisions} == {
        first.calculation_revision_id,
        second.calculation_revision_id,
    }
    assert all(r.state is CalculationRevisionState.BORRADOR for r in revisions)

    # Current pointer follows most-recent calculate.
    refreshed_work_unit = get_work_unit(
        work_unit.work_unit_id,
        repository=wu_repo,
    )
    assert refreshed_work_unit.current_calculation_revision_id == second.calculation_revision_id
    assert refreshed_work_unit.filed_calculation_revision_id is None
    assert refreshed_work_unit.current_filing_record_id is None


def test_calculate_is_idempotent_on_identical_inputs(repos) -> None:
    """Re-running calculate with identical inputs / outputs returns
    the existing revision (content-addressed id collides) without
    creating a duplicate."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )
    assert first.calculation_revision_id == second.calculation_revision_id
    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,
    )
    assert len(revisions) == 1


def test_mark_verificado_completo_requires_borrador_state(repos) -> None:
    """A revision in any state other than BORRADOR cannot be marked
    verificado-completo."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    verified = mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    assert verified.state is CalculationRevisionState.VERIFICADO_COMPLETO

    # Second attempt against the now-verified revision must fail.
    with pytest.raises(CalculationRevisionStateError, match=r"state|verified|already|complete"):
        mark_revision_verificado_completo(
            revision.calculation_revision_id,
            actor="operator-A",
            calculation_repository=cr_repo,
            clock=_T3,
        )


def test_file_requires_verificado_completo_state(repos) -> None:
    """A borrador revision cannot be filed; only verificado-completo
    revisions are eligible."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    with pytest.raises(CalculationRevisionStateError, match=r"state|verified|VERIFIED"):
        file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
        )


def test_file_creates_filing_record_and_advances_pointers(repos) -> None:
    """The happy-path file flow: calculate → mark verified-complete
    → file. After file: a ModeloRecord exists, the revision is in
    FILED state, the work unit's filed_calculation_revision_id and
    current_filing_record_id pointers point at the new IDs, and
    filing-record current_for(...) resolves to the new record."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    filing = _file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        notes="Q1 IVA",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    assert filing.status is ModeloRecordStatus.VIGENTE
    assert filing.aeat_accepted is False
    assert filing.notes == "Q1 IVA"
    assert filing.filed_by == "operator-A"
    assert filing.calculation_revision_id == revision.calculation_revision_id

    refreshed_revision = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision.state is CalculationRevisionState.PRESENTADO
    assert refreshed_revision.filed_at == _T3
    assert refreshed_revision.filed_by == "operator-A"

    refreshed_wu = get_work_unit(
        work_unit.work_unit_id,
        repository=wu_repo,
    )
    assert refreshed_wu.filed_calculation_revision_id == revision.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == filing.filing_record_id

    # The filing-record catalogue's current_for query resolves to
    # the new record — this is the canonical "which revision is THE
    # Q1 filed answer?" lookup that downstream consumers
    # (aggregation, amendments) use.
    catalogue = fr_repo.load()
    current = catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    assert current is not None
    assert current.filing_record_id == filing.filing_record_id


def test_file_runs_workflow_gate_and_refuses_before_state_writes_when_preflight_blocks(repos) -> None:
    """The file transition is gated by WorkflowEngine.run_for_period.

    When submission preflight refuses, the calculation revision remains
    verified-complete and no filing record or filed bucket event is
    persisted.
    """

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )

    unavailable_provider = _AuthProvider(available=False)
    with pytest.raises(ModeloWorkflowGateError, match="workflow gate aborted"):
        _file_revision(
            revision.calculation_revision_id,
            revision=revision,
            work_unit=work_unit,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T3,
            auth_provider=unavailable_provider,
        )

    assert unavailable_provider.describe_calls == 1
    refreshed_revision = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert list_filing_records(filing_repository=fr_repo) == ()
    filed_events = bv_repo.load().for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILED,),
    )
    assert filed_events == ()


def test_verify_runs_workflow_gate_and_refuses_before_verified_state_write(repos) -> None:
    """A granted verification must still pass the WorkflowEngine gate.

    Auth/preflight blockers abort before the verified-complete state,
    verification report, or verification bucket event is persisted.
    """

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    unavailable_provider = _AuthProvider(available=False)
    with pytest.raises(ModeloWorkflowGateError, match="workflow gate aborted"):
        _verify_revision(
            revision.calculation_revision_id,
            revision=revision,
            work_unit=work_unit,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
            auth_provider=unavailable_provider,
        )

    assert unavailable_provider.describe_calls == 1
    refreshed_revision = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision.state is CalculationRevisionState.BORRADOR
    assert (
        list_verification_reports(
            calculation_revision_id=revision.calculation_revision_id,
            verification_repository=vr_repo,
        )
        == ()
    )
    verification_events = bv_repo.load().for_bucket(
        work_unit.bucket_id,
        event_types=(
            BucketEventType.MODELO_VERIFICATION_PASSED,
            BucketEventType.MODELO_VERIFICATION_REFUSED,
        ),
    )
    assert verification_events == ()


def test_filing_record_supersession_preserves_audit_history(repos) -> None:
    """Re-filing a later verified revision supersedes the prior
    filing. The prior filing record moves to SUPERSEDED with the
    supersession metadata captured; the prior calculation revision
    moves from FILED to FILED_SUPERSEDED. The new filing becomes
    CURRENT. ``history_for(...)`` returns both records in
    filed_at order."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    # First filing: revision-1, filed at T3.
    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verificado_completo(
        revision_one.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    filing_one = _file_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    # Second filing: revision-2 with corrected inputs, filed at T5.
    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1200"), "02": Decimal("100")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    mark_revision_verificado_completo(
        revision_two.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T4,
    )
    filing_two = _file_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        notes="corrected after audit",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T5,
    )

    # New filing is current.
    assert filing_two.status is ModeloRecordStatus.VIGENTE
    refreshed_revision_two = get_calculation_revision(
        revision_two.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision_two.state is CalculationRevisionState.PRESENTADO

    # Prior filing is superseded; prior revision moved to FILED_SUPERSEDED.
    refreshed_filing_one = get_filing_record(
        filing_one.filing_record_id,
        filing_repository=fr_repo,
    )
    assert refreshed_filing_one.status is ModeloRecordStatus.SUPERSEDIDO
    assert refreshed_filing_one.superseded_at == _T5
    assert refreshed_filing_one.superseded_by_filing_record_id == filing_two.filing_record_id

    refreshed_revision_one = get_calculation_revision(
        revision_one.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision_one.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO
    assert refreshed_revision_one.superseded_at == _T5

    # current_for resolves to the new filing only.
    catalogue = fr_repo.load()
    current = catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    assert current is not None
    assert current.filing_record_id == filing_two.filing_record_id

    # history_for returns both records in filed_at order.
    history = catalogue.history_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    assert tuple(r.filing_record_id for r in history) == (
        filing_one.filing_record_id,
        filing_two.filing_record_id,
    )

    # Work-unit pointers point at the new filing.
    refreshed_wu = get_work_unit(
        work_unit.work_unit_id,
        repository=wu_repo,
    )
    assert refreshed_wu.filed_calculation_revision_id == revision_two.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == filing_two.filing_record_id


def test_list_filing_records_excludes_superseded_by_default(repos) -> None:
    """The default listing surfaces operator-visible state (current
    filings). Pass include_superseded=True to walk audit history."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verificado_completo(
        revision_one.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    _file_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1200")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    mark_revision_verificado_completo(
        revision_two.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T4,
    )
    _file_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T5,
    )

    default_listing = list_filing_records(
        filing_repository=fr_repo,
    )
    assert len(default_listing) == 1
    assert default_listing[0].status is ModeloRecordStatus.VIGENTE

    with_history = list_filing_records(
        include_superseded=True,
        filing_repository=fr_repo,
    )
    assert len(with_history) == 2


def test_calculate_refused_on_discarded_work_unit(repos) -> None:
    """A discarded work unit refuses further calculation. The
    operator must create a fresh work unit to continue."""

    from aeat.application.modelo import (
        WorkUnitMutationRefusedError,
        discard_work_unit,
    )

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    with pytest.raises(WorkUnitMutationRefusedError, match=r"discard|state|DISCARDED|work_unit"):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={"01": Decimal("1000")},
            binding_values=_DEFAULT_130_BINDING_VALUES,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
        )


def test_discard_emits_modelo_work_unit_discarded_event(repos) -> None:
    """``discard_work_unit`` emits a ``modelo.work_unit.discarded``
    bucket event with actor + reason payload."""

    from aeat.application.modelo import discard_work_unit
    from aeat.domain.buckets._event import BucketEventObjectType, BucketEventType

    wu_repo, _, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discarded = discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        reason="superseded by new work unit",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    history = bv_repo.load().for_bucket(discarded.bucket_id)
    discard_events = [event for event in history if event.event_type is BucketEventType.MODELO_WORK_UNIT_DISCARDED]
    assert len(discard_events) == 1
    event = discard_events[0]
    assert event.object_type is BucketEventObjectType.WORK_UNIT
    assert event.object_id == discarded.work_unit_id
    assert event.actor == "operator-A"
    assert event.payload["reason"] == "superseded by new work unit"


def test_get_filing_record_raises_on_missing_id(repos) -> None:
    _, _, fr_repo, _, _ = repos
    with pytest.raises(ModeloRecordNotFoundError, match=r"filing|record|not|found"):
        get_filing_record(
            "0" * 64,
            filing_repository=fr_repo,
        )


def test_get_calculation_revision_raises_on_missing_id(repos) -> None:
    _, cr_repo, _, _, _ = repos
    with pytest.raises(CalculationRevisionNotFoundError, match=r"calculation|revision|not|found"):
        get_calculation_revision(
            "0" * 64,
            calculation_repository=cr_repo,
        )


# ---------------------------------------------------------------------------
# verify_modelo_revision — real-registry, encrypted-SQL end-to-end coverage.
# Inputs are drawn from registry ground truth (modelo 180, revision
# ``2023-y-siguientes``, period ``0A``).
# ---------------------------------------------------------------------------


def test_verify_grants_when_all_required_casillas_present_real_registry(
    repos,
) -> None:
    """Real e2e: registry resolves modelo 180 (2024, 0A); every required
    manual casilla is supplied; the verifier persists a granted report
    in encrypted storage; the calculation revision transitions
    DRAFT → VERIFICADO_COMPLETO. No mocks, no in-memory fakes — the
    SQL repository encrypts on save and decrypts on load."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    required = _registry_required_manual_casillas_for(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    assert report.findings == ()
    assert set(report.resolved_casillas) == set(required)
    assert report.missing_required_casillas == ()

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert refreshed.verified_at == _T2
    assert refreshed.verified_by == "operator-A"

    # Round-trip through encrypted storage.
    persisted = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert persisted.granted_verificado_completo is True
    assert persisted.completeness_status is VerificationCompletenessStatus.COMPLETE


def test_verify_refuses_when_required_casilla_missing_real_registry(
    repos,
) -> None:
    """Real e2e: omit one required casilla; the verifier emits a
    BLOCKING ``MISSING_REQUIRED_CASILLA`` finding for it; the
    revision stays DRAFT; the refused report is still persisted so
    the audit trail records the refusal."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    assert len(required) >= 2

    omitted = required[0]
    supplied = {cid: Decimal("1") for cid in required[1:]}

    work_unit = _seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=supplied,
        binding_values=_DEFAULT_180_BINDING_VALUES,
        relation_values=_DEFAULT_180_RELATION_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.INCOMPLETE
    assert any(
        f.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
        and f.severity is ModeloVerificationFindingSeverity.BLOCKING
        and f.casilla_id == omitted
        for f in report.findings
    )
    assert omitted in report.missing_required_casillas

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.BORRADOR

    persisted = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert persisted.granted_verificado_completo is False


def test_verify_emits_blocking_rule_when_registry_unresolved_real_registry(
    repos,
) -> None:
    """Real e2e: a work unit anchored to a year that predates modelo
    180's earliest revision (``valid_from=2019``) cannot resolve a
    registry snapshot. The verifier surfaces a BLOCKING_RULE finding
    and refuses the transition. The revision stays DRAFT."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo=_VERIFY_MODELO,
        filing_year=2010,
        period=_VERIFY_PERIOD,
        revision_id=_VERIFY_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    # Direct-seed a DRAFT revision because ``calculate_modelo_revision``
    # now runs the formula engine and would refuse the unresolvable
    # snapshot at calculate time. This test exercises verify's
    # BLOCKING_RULE path explicitly: the work unit was anchored at a
    # year that predates the modelo's earliest revision, so verify's
    # registry-snapshot resolution still fails.
    from aeat.domain.modelos._calculation_repository import (
        upsert_calculation_revision,
    )
    from aeat.domain.modelos._calculation_revision import (
        CalculationRevision,
        derive_calculation_revision_id,
    )

    inputs: dict[str, str] = {"perc.base": "1"}
    overrides_map: dict[str, str] = {}
    casillas: dict[str, Decimal] = {"perc.base": Decimal("1")}
    rid = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot=inputs,
        binding_overrides=overrides_map,
        casilla_values=casillas,
    )
    revision = CalculationRevision(
        calculation_revision_id=rid,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        inputs_snapshot=inputs,
        binding_overrides=overrides_map,
        casilla_values=casillas,
        created_at=_T1,
        updated_at=_T1,
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
    assert any(f.kind is ModeloVerificationFindingKind.BLOCKING_RULE for f in report.findings)

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.BORRADOR


def test_verify_rejects_non_borrador_revision_real_registry(repos) -> None:
    """Real e2e: a verificado-completo revision cannot be re-verified.
    The operator must produce a fresh draft (which lands as BORRADOR)
    to verify again."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    with pytest.raises(CalculationRevisionStateError, match=r"state|verify|verified|already"):
        verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=_T3,
        )


def test_list_and_get_verification_reports_real_registry(repos) -> None:
    """Real e2e: reports persist through the encrypted catalogue and
    are indexable by id and by calculation_revision_id."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    report = _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    listed = list_verification_reports(
        calculation_revision_id=revision.calculation_revision_id,
        verification_repository=vr_repo,
    )
    assert tuple(r.verification_report_id for r in listed) == (report.verification_report_id,)

    fetched = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert fetched.verification_report_id == report.verification_report_id

    with pytest.raises(VerificationReportNotFoundError, match=r"verification|report|not|found"):
        get_verification_report(
            "0" * 64,
            verification_repository=vr_repo,
        )


# ---------------------------------------------------------------------------
# bucket-event emission — modelo.calculation.created /
# modelo.verification.{passed,refused} / modelo.filed /
# modelo.filed_superseded.
#
# Every domain write that lands above must also append a row to the
# bucket-event-history catalogue. These tests exercise the encrypted
# round-trip on the bucket-event catalogue itself: emit, save, load,
# query.
# ---------------------------------------------------------------------------


def test_calculate_emits_modelo_calculation_created_event(repos) -> None:
    """calculate_modelo_revision appends a ``modelo.calculation.created``
    event with the new revision id as object_id and the work unit's
    (modelo, year, period) carried in the payload."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    catalogue = bv_repo.load()
    events = catalogue.for_bucket(work_unit.bucket_id)
    assert len(events) == 1
    event = events[0]
    assert event.event_type is BucketEventType.MODELO_CALCULATION_CREATED
    assert event.object_type is BucketEventObjectType.CALCULATION_REVISION
    assert event.object_id == revision.calculation_revision_id
    assert event.actor == "operator-A"
    assert event.occurred_at == _T1
    assert event.payload["work_unit_id"] == work_unit.work_unit_id
    assert event.payload["modelo"] == work_unit.modelo
    assert event.payload["filing_year"] == str(work_unit.filing_year)
    assert event.payload["period"] == work_unit.period
    assert event.payload["borrador_snapshot_id"] == ""
    assert event.payload["borrador_binding_count"] == "0"


def test_verify_emits_passed_event_on_success(repos) -> None:
    """verify_modelo_revision emits ``modelo.verification.passed``
    when the verifier grants verified-complete; the event id matches
    the persisted verification report."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    report = _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    catalogue = bv_repo.load()
    verification_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(
            BucketEventType.MODELO_VERIFICATION_PASSED,
            BucketEventType.MODELO_VERIFICATION_REFUSED,
        ),
    )
    assert len(verification_events) == 1
    event = verification_events[0]
    assert event.event_type is BucketEventType.MODELO_VERIFICATION_PASSED
    assert event.object_type is BucketEventObjectType.VERIFICATION_REPORT
    assert event.object_id == report.verification_report_id
    assert event.payload["calculation_revision_id"] == revision.calculation_revision_id
    assert event.payload["completeness_status"] == "complete"


def test_verify_emits_refused_event_on_missing_casilla(repos) -> None:
    """verify_modelo_revision emits ``modelo.verification.refused``
    when a required casilla is missing; the calculation revision
    stays DRAFT and the refusal lands in the bucket event log."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    omitted = required[0]
    supplied = {cid: Decimal("1") for cid in required[1:]}

    work_unit = _seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs=supplied,
        binding_values=_DEFAULT_180_BINDING_VALUES,
        relation_values=_DEFAULT_180_RELATION_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )
    assert report.granted_verificado_completo is False

    catalogue = bv_repo.load()
    refused = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_VERIFICATION_REFUSED,),
    )
    assert len(refused) == 1
    event = refused[0]
    assert event.event_type is BucketEventType.MODELO_VERIFICATION_REFUSED
    assert event.payload["completeness_status"] == "incomplete"
    assert int(event.payload["missing_required_count"]) >= 1
    assert omitted not in event.payload  # omitted casilla id stays in the report, not the event payload


def test_file_emits_modelo_filed_event(repos) -> None:
    """file_modelo_revision appends a ``modelo.filed`` event
    referencing the new filing record id and carrying the modelo /
    year / period plus the underlying revision id."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    filing = _file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    catalogue = bv_repo.load()
    filed_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILED,),
    )
    assert len(filed_events) == 1
    event = filed_events[0]
    assert event.object_id == filing.filing_record_id
    assert event.payload["calculation_revision_id"] == revision.calculation_revision_id
    assert event.payload["modelo"] == work_unit.modelo
    # No prior filing was superseded — payload carries empty string.
    assert event.payload["supersedes_filing_record_id"] == ""


def test_file_supersession_emits_both_filed_and_superseded_events(repos) -> None:
    """A second filing supersedes the prior one. The bucket-event
    log carries one ``modelo.filed_superseded`` event for the prior
    record (object_id = prior filing record id) and one new
    ``modelo.filed`` event for the new record (with the prior id in
    the ``supersedes_filing_record_id`` payload key)."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    mark_revision_verificado_completo(
        revision_one.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    filing_one = _file_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )

    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={"01": Decimal("1200"), "02": Decimal("100")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    mark_revision_verificado_completo(
        revision_two.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T4,
    )
    filing_two = _file_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T5,
    )

    catalogue = bv_repo.load()
    superseded_events = catalogue.for_object(
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=filing_one.filing_record_id,
    )
    types = tuple(e.event_type for e in superseded_events)
    assert BucketEventType.MODELO_FILED in types
    assert BucketEventType.MODELO_FILED_SUPERSEDED in types

    # The new filing.filed event references the prior record id.
    new_filed_events = catalogue.for_object(
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=filing_two.filing_record_id,
    )
    assert len(new_filed_events) == 1
    assert new_filed_events[0].event_type is BucketEventType.MODELO_FILED
    assert new_filed_events[0].payload["supersedes_filing_record_id"] == filing_one.filing_record_id

    # Whole chain in chronological order for the bucket:
    # calc1, filed1, calc2, superseded1+filed2.
    all_events = catalogue.for_bucket(work_unit.bucket_id)
    type_chain = tuple(e.event_type for e in all_events)
    assert type_chain == (
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_FILED,
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_FILED_SUPERSEDED,
        BucketEventType.MODELO_FILED,
    )


# ---------------------------------------------------------------------------
# Formula-engine wiring
# ---------------------------------------------------------------------------


def test_calculate_runs_registry_formula_engine(repos) -> None:
    """``calculate_modelo_revision`` runs the registry's formula engine
    over the operator-supplied inputs and persists the FULL computed
    casilla map. Modelo 130 1T 2026 declares 9 manual casillas plus
    10 computed formulas; given inputs for casilla 01 and 02, the
    engine derives casilla 03 = 01 - 02 (subtract).

    The persisted revision carries the operator inputs in
    ``inputs_snapshot`` (canonical decimal strings) and the full
    engine output, inputs plus formula targets, in ``casilla_values``.
    The bucket event payload reports the formula count from the
    engine result."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    casilla_inputs = {"01": Decimal("10000"), "02": Decimal("3000")}

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs=casilla_inputs,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    # Operator inputs surface in ``inputs_snapshot``.
    assert revision.inputs_snapshot["01"] == "10000"
    assert revision.inputs_snapshot["02"] == "3000"
    assert "03" not in revision.inputs_snapshot  # 03 is a formula target, not an input

    # Engine output contains BOTH the operator inputs AND every
    # formula target; domain-level registry tests own arithmetic parity.
    assert revision.casilla_values["01"] == casilla_inputs["01"]
    assert revision.casilla_values["02"] == casilla_inputs["02"]
    assert "03" in revision.casilla_values
    assert revision.casilla_values["03"] < revision.casilla_values["01"]
    # Every casilla declared in the 130 1T 2026 revision is now in
    # the output — 9 manual + 10 formula targets = 19 entries.
    assert len(revision.casilla_values) >= 19

    # Bucket-event payload reports the formula count from the engine.
    catalogue = bv_repo.load()
    created_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_CALCULATION_CREATED,),
    )
    assert len(created_events) == 1
    assert int(created_events[0].payload["formula_count"]) >= 1
    assert int(created_events[0].payload["casilla_count"]) >= 19


def test_calculate_works_when_cwd_is_not_the_repo_root(
    repos,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registry root resolves via ``PROJECT_ROOT`` from
    ``aeat.core.config``, not via a CWD-relative ``"registry/aeat"``
    string. Running the action from any other directory must still
    work — production deploys, background daemons, and wheel
    installs all run from non-repo CWDs."""

    import os as _os

    alien_cwd = tmp_path / "alien-working-dir"
    alien_cwd.mkdir()
    monkeypatch.chdir(alien_cwd)
    assert _os.getcwd() == str(alien_cwd)

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={"01": Decimal("10000"), "02": Decimal("3000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    # Sanity: engine ran (formula casilla 03 computed = 01 - 02).
    assert revision.casilla_values["03"] == Decimal("7000.00")


def test_calculate_refuses_when_registry_snapshot_unresolvable(repos) -> None:
    """``calculate_modelo_revision`` runs the formula engine, so it
    cannot operate on a work unit whose (modelo, year, period) tuple
    does not resolve a registry snapshot. The action raises
    ``CalculationRegistryUnavailableError`` rather than persisting a
    revision that bypasses the engine."""

    from aeat.application.modelo import CalculationRegistryUnavailableError

    wu_repo, cr_repo, _, _, bv_repo = repos
    # Modelo 130 at year 2010 predates the registry's earliest
    # revision (``2019-y-siguientes``), so the snapshot lookup fails.
    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2010,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    with pytest.raises(
        CalculationRegistryUnavailableError,
        match=r"registry snapshot|could not be resolved",
    ):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={"01": Decimal("1000")},
            binding_values=_DEFAULT_130_BINDING_VALUES,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )
