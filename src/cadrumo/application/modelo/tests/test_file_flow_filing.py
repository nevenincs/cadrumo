"""Modelo file-flow application tests split by workflow."""

from __future__ import annotations

import pytest

from ....core import Period
from ...calculations import CalculationObservationRepository
from ...workflow.persistence import WorkflowRunRepository
from ...workflow.run_models import WorkflowDeadlineContextDetails
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_EXPENSE_CASILLA,
    M130_INCOME_CASILLA,
    T1,
    T2,
    T3,
    T4,
    T5,
    CalculationRevisionState,
    CalculationRevisionStateError,
    Decimal,
    ModeloRecordNotFoundError,
    ModeloRecordStatus,
    ModeloWorkflowGateError,
    Repos,
    WorkflowAbortReason,
    WorkflowStage,
    calculate_modelo_revision,
    file_modelo_revision,
    file_revision,
    get_calculation_revision,
    get_filing_record,
    get_work_unit,
    list_filing_records,
    seed_work_unit,
    target_filing_records,
    verify_revision,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_BUCKET_ID = "12121212-1212-4212-8212-121212121212"


def test_file_requires_verificado_completo_state(repos: Repos) -> None:
    """A borrador revision cannot be filed; only verificado-completo
    revisions are eligible."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    with pytest.raises(CalculationRevisionStateError, match=r"state|verified|VERIFIED") as raised:
        file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=T2,
        )
    failure = raised.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.file.calculation_revision.unverified"
    assert raised.value.terminal_precondition_verdict is failure.verdict
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == "operator.modelo.work.verify"
    assert failure.verdict.argument_bindings[0].value == work_unit.work_unit_id


def test_file_creates_filing_record_and_advances_pointers(repos: Repos) -> None:
    """The happy-path file flow: calculate → verify
    → file. After file: a ModeloRecord exists, the revision is in
    FILED state, the work unit's filed_calculation_revision_id and
    current_filing_record_id pointers point at the new IDs, and
    filing-record current_for(...) resolves to the new record."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    filing = file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        notes="Q1 IVA",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
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
    assert refreshed_revision.filed_at == T3
    assert refreshed_revision.filed_by == "operator-A"

    refreshed_wu = get_work_unit(
        work_unit.work_unit_id,
        repository=wu_repo,
    )
    assert refreshed_wu.current_calculation_revision_id == revision.calculation_revision_id
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


def test_file_records_verified_modelo_130_2024_as_late_non_official_local_filing(repos: Repos) -> None:
    """A real historical M130 obligation can be marked filed locally after verification."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    filing = file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    assert filing.status is ModeloRecordStatus.VIGENTE
    assert filing.aeat_accepted is False
    assert filing.external_evidence is None
    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.PRESENTADO
    assert get_work_unit(work_unit.work_unit_id, repository=wu_repo).filed_calculation_revision_id == (
        revision.calculation_revision_id
    )
    observation = CalculationObservationRepository().load_observation(
        "130",
        Period.from_year_and_code(2024, "1T"),
    )
    assert observation is not None
    assert observation.source_kind == APP_FILING_SOURCE_KIND
    assert APP_FILING_SOURCE_KIND == "app_filing"

    workflow_runs = WorkflowRunRepository(objects=bv_repo.secure_object_repository).list()
    target_run = next(
        run
        for run in workflow_runs
        if run.obligation is not None and run.obligation.modelo == "130" and run.obligation.period == work_unit.period
    )
    assert target_run.final_stage is WorkflowStage.DONE
    computing = next(step for step in target_run.steps if step.stage is WorkflowStage.COMPUTING_DEADLINES)
    assert computing.success is True
    assert isinstance(computing.details, WorkflowDeadlineContextDetails)
    assert computing.details.overdue is True
    assert computing.details.extemporanea is True

    assert target_filing_records(list_filing_records(filing_repository=fr_repo), work_unit) == (filing,)


def test_file_refuses_future_period_before_filing_window_opens(repos: Repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2026, period="3T")
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={
            **DEFAULT_130_BINDING_VALUES,
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    with pytest.raises(ModeloWorkflowGateError) as gate_error:
        file_revision(
            revision.calculation_revision_id,
            revision=revision,
            work_unit=work_unit,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=T3,
        )

    assert gate_error.value.result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION
    terminal_step = gate_error.value.result.steps[-1]
    assert terminal_step.summary_locale_key == "application.workflow.steps.deadline_future"
    assert isinstance(terminal_step.details, WorkflowDeadlineContextDetails)
    assert terminal_step.details.filing_window is not None
    assert terminal_step.details.filing_window.value == "future"
    assert terminal_step.precondition_verdict is not None
    assert terminal_step.precondition_verdict.failed_condition_id == "workflow.deadline.filing_window_open"
    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert target_filing_records(list_filing_records(filing_repository=fr_repo), work_unit) == ()


def test_file_records_overdue_modelo_130_2025_as_late_local_filing(repos: Repos) -> None:
    """A real but closed M130/2025 obligation can still seed the local carry chain."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2025)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    filing = file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    assert filing.status is ModeloRecordStatus.VIGENTE
    assert filing.aeat_accepted is False
    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.PRESENTADO
    assert get_work_unit(work_unit.work_unit_id, repository=wu_repo).filed_calculation_revision_id == (
        revision.calculation_revision_id
    )


def test_filing_record_supersession_preserves_audit_history(repos: Repos) -> None:
    """Re-filing a later verified revision supersedes the prior
    filing. The prior filing record moves to SUPERSEDED with the
    supersession metadata captured; the prior calculation revision
    moves from FILED to FILED_SUPERSEDED. The new filing becomes
    CURRENT. ``history_for(...)`` returns both records in
    filed_at order."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)

    # First filing: revision-1, filed at T3.
    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    verify_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    filing_one = file_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    # Second filing: revision-2 with corrected inputs, filed at T5.
    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            **DEFAULT_130_BASELINE_INPUTS,
            M130_INCOME_CASILLA: Decimal("1200"),
            M130_EXPENSE_CASILLA: Decimal("100"),
        },
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T4,
    )
    verify_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T4,
    )
    filing_two = file_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        notes="corrected after audit",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T5,
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
    assert refreshed_filing_one.superseded_at == T5
    assert refreshed_filing_one.superseded_by_filing_record_id == filing_two.filing_record_id

    refreshed_revision_one = get_calculation_revision(
        revision_one.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision_one.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO
    assert refreshed_revision_one.superseded_at == T5

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


def test_list_filing_records_excludes_superseded_by_default(repos: Repos) -> None:
    """The default listing surfaces operator-visible state (current
    filings). Pass include_superseded=True to walk audit history."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)

    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    verify_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    file_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1200")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T4,
    )
    verify_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T4,
    )
    file_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T5,
    )

    default_listing = list_filing_records(
        filing_repository=fr_repo,
    )
    target_default_listing = target_filing_records(default_listing, work_unit)
    assert len(target_default_listing) == 1
    assert target_default_listing[0].status is ModeloRecordStatus.VIGENTE

    with_history = list_filing_records(
        include_superseded=True,
        filing_repository=fr_repo,
    )
    assert len(target_filing_records(with_history, work_unit)) == 2


def test_list_filing_records_orders_multiple_periods_without_period_comparison(repos: Repos) -> None:
    from ....domain.modelos import ModeloCode, ModeloRecord, ModeloRecordCatalogue, derive_filing_record_id

    _, _, fr_repo, _, _ = repos
    q1 = Period.from_year_and_code(2025, "1T")
    q2 = Period.from_year_and_code(2025, "2T")
    record_1 = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id="1" * 64,
            calculation_revision_id="2" * 64,
            filed_by="operator-A",
        ),
        work_unit_id="1" * 64,
        calculation_revision_id="2" * 64,
        bucket_id=_FILING_BUCKET_ID,
        modelo=ModeloCode("130"),
        filing_year=2025,
        period=q1,
        filed_at=T1,
        filed_by="operator-A",
    )
    record_2 = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id="3" * 64,
            calculation_revision_id="4" * 64,
            filed_by="operator-A",
        ),
        work_unit_id="3" * 64,
        calculation_revision_id="4" * 64,
        bucket_id=_FILING_BUCKET_ID,
        modelo=ModeloCode("130"),
        filing_year=2025,
        period=q2,
        filed_at=T2,
        filed_by="operator-A",
    )
    fr_repo.save(
        ModeloRecordCatalogue(
            records={
                record_2.filing_record_id: record_2,
                record_1.filing_record_id: record_1,
            },
        ),
    )

    listed = list_filing_records(filing_repository=fr_repo)

    assert tuple(record.period.registry_token for record in listed) == ("1T", "2T")


def test_list_filing_records_filters_by_modelo(repos: Repos) -> None:
    from ....domain.modelos import ModeloCode, ModeloRecord, ModeloRecordCatalogue, derive_filing_record_id

    _, _, fr_repo, _, _ = repos
    period = Period.from_year_and_code(2025, "0A")
    record_100 = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id="1" * 64,
            calculation_revision_id="2" * 64,
            filed_by="operator-A",
        ),
        work_unit_id="1" * 64,
        calculation_revision_id="2" * 64,
        bucket_id=_FILING_BUCKET_ID,
        modelo=ModeloCode("100"),
        filing_year=2025,
        period=period,
        filed_at=T1,
        filed_by="operator-A",
    )
    record_130 = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id="3" * 64,
            calculation_revision_id="4" * 64,
            filed_by="operator-A",
        ),
        work_unit_id="3" * 64,
        calculation_revision_id="4" * 64,
        bucket_id=_FILING_BUCKET_ID,
        modelo=ModeloCode("130"),
        filing_year=2025,
        period=period,
        filed_at=T2,
        filed_by="operator-A",
    )
    fr_repo.save(
        ModeloRecordCatalogue(
            records={
                record_100.filing_record_id: record_100,
                record_130.filing_record_id: record_130,
            },
        ),
    )

    listed = list_filing_records(modelo="100", filing_repository=fr_repo)

    assert tuple(record.modelo for record in listed) == (ModeloCode("100"),)


def test_get_filing_record_raises_on_missing_id(repos: Repos) -> None:
    _, _, fr_repo, _, _ = repos
    with pytest.raises(ModeloRecordNotFoundError) as excinfo:
        get_filing_record(
            "0" * 64,
            filing_repository=fr_repo,
        )
    assert excinfo.value.translated_message == "application.modelo.errors.filing_record_not_found"
