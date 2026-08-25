"""Tests for the workflow resumption action."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.workflow.abort import WorkflowAbortReason
from cadrumo.application.workflow.errors import WorkflowError
from cadrumo.application.workflow.persistence import load_run, save_run
from cadrumo.application.workflow.resume import (
    WorkflowResumeContext,
    WorkflowResumeRefusedError,
    WorkflowResumeRunAmbiguousError,
    find_latest_run_for_period,
    find_unique_run_for_period,
    resolve_modelo_exact_workflow_run_for_resume,
    resolve_modelo_visible_workflow_run_for_resume,
    resolve_modelo_workflow_resume_target,
    resolve_modelo_workflow_run_for_resume,
    resume_modelo_workflow,
)
from cadrumo.application.workflow.run_models import WorkflowObligationFacts, WorkflowResult, WorkflowStage, WorkflowStep

from ....adapters.outbound.aeat.browser import SiteHealthEvidence, SiteHealthState, SiteHealthStatus
from ....adapters.outbound.aeat.browser._site_health import _URL_ADAPTER
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import (
    ActionConditionality,
    ActionEvidenceProvenance,
    CasillaId,
    Modelo,
    NoRecoveryOutcome,
    Period,
    validated_casilla_id,
)
from ....core.errors import SiteHealthError, resolve_error_message
from ....domain.calculations.registry import CasillaObservation
from ....domain.deadlines import ObligationStatus
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.aeat_literal_fixtures import aeat_url
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo._selectors import ModeloCalculationRevisionSelector
from ...modelo._work_lifecycle import create_work_unit
from ...modelo._workflow_gate import workflow_period_for_work_unit
from ...modelo.work_addressing import ModeloExactWorkUnitTarget, ModeloVisibleFilingTarget
from ...operator_actions import (
    ConditionEvidence,
    PreconditionVerdict,
)
from ..engine_recording import record_site_unavailable, record_unhandled
from ..errors import WorkflowAbortSignalError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_T = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
_BUCKET_ID = "a38b7cd5-d38e-4d69-809f-5a244c74e08b"
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Resume"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value="false"),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value="false"),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value="false"),
    UserProfileFact(
        path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
        value="false",
    ),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def _seed_ready_profile_record(bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T,
            updated_at=_T,
        ),
        # Derived, never the bare id: a capsule label may not be UUID-shaped,
        # so an operator label can never be read as a machine id.
        label=f"profile-{bucket_id}",
    )


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_ready_profile_record(_BUCKET_ID)
        yield


_RESUME_CASILLA: CasillaId = validated_casilla_id("01")


def _obligation(modelo: str = "130", period: Period | None = None) -> WorkflowObligationFacts:
    period = period or Period.from_year_and_code(2026, "1T")
    return WorkflowObligationFacts(
        modelo=Modelo(modelo),
        period=period,
        opens_on=date(2026, 4, 1),
        closes_on=date(2026, 4, 20),
        status=ObligationStatus.UPCOMING,
    )


def _abort_verdict(reason: WorkflowAbortReason) -> PreconditionVerdict:
    """Build the closed terminal state represented by a persisted resume fixture."""
    if reason in {WorkflowAbortReason.NO_PENDING_OBLIGATION, WorkflowAbortReason.DEADLINE_PASSED}:
        condition_id = "workflow.deadline.filing_window_open"
        evidence_id = "workflow.deadline.window"
        provenance = ActionEvidenceProvenance.DOMAIN_EVALUATION
        values: dict[str, str | bool] = {"filing_window_open": False}
    elif reason is WorkflowAbortReason.ALREADY_FILED:
        condition_id = "workflow.obligation.unfiled"
        evidence_id = "workflow.obligation.filing_state"
        provenance = ActionEvidenceProvenance.RUNTIME_OBSERVATION
        values = {"unfiled": False}
    else:
        condition_id = "workflow.execution.completed"
        evidence_id = "workflow.execution.error_code"
        provenance = ActionEvidenceProvenance.RUNTIME_OBSERVATION
        values = {"completed": False, "error_code": f"workflow.execution.{reason.value.lower()}"}
    outcome = (
        NoRecoveryOutcome.OPERATOR_DECISION
        if reason in {WorkflowAbortReason.SITE_UNAVAILABLE, WorkflowAbortReason.UNHANDLED_EXCEPTION}
        else NoRecoveryOutcome.TERMINAL
    )
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=evidence_id,
                provenance=provenance,
                values=values,
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=outcome,
    )


def _aborted_result(
    *,
    run_id: str,
    reason: WorkflowAbortReason,
    obligation: WorkflowObligationFacts | None,
) -> WorkflowResult:
    verdict = _abort_verdict(reason)
    step = WorkflowStep(
        stage=WorkflowStage.BUILDING_DRAFT,
        started_at=_T,
        ended_at=_T,
        success=False,
        summary_locale_key="application.workflow.steps.workflow_failure",
        precondition_verdict=verdict,
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=reason,
        obligation=obligation,
        steps=(step,),
        summary_locale_key="application.workflow.results.aborted",
    )


def _recorded_operational_result(
    *,
    run_id: str,
    reason: WorkflowAbortReason,
    steps: list[WorkflowStep],
) -> WorkflowResult:
    """Materialize the real recorder output as one persisted aborted workflow run."""
    terminal = steps[-1]
    assert terminal.details is not None
    assert terminal.ended_at is not None
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=terminal.ended_at,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=reason,
        obligation=_obligation(),
        steps=tuple(steps),
        summary_locale_key="application.workflow.results.aborted",
        summary_details=terminal.details,
    )


def test_site_unavailable_recorder_persists_a_resumable_operator_decision() -> None:
    """The real site-health recorder stays consistent with the resume authority."""
    run_id = "7" * 16
    status = SiteHealthStatus(
        state=SiteHealthState.MANTENIMIENTO,
        evidence=SiteHealthEvidence(
            url=_URL_ADAPTER.validate_python(aeat_url("sede", "/")),
            http_status=503,
            html_fragment="<html>servicio temporalmente no disponible</html>",
            detected_markers=("servicio temporalmente no disponible",),
        ),
        observed_at=_T,
    )
    steps: list[WorkflowStep] = []

    def current_run_id() -> str:
        return run_id

    with pytest.raises(WorkflowAbortSignalError) as raised:
        record_site_unavailable(
            stage=WorkflowStage.RUNNING_PREFLIGHT,
            started=_T,
            exc=SiteHealthError(status=status),
            steps=steps,
            current_run_id=current_run_id,
        )

    assert raised.value.reason is WorkflowAbortReason.SITE_UNAVAILABLE
    persisted = _recorded_operational_result(
        run_id=run_id,
        reason=raised.value.reason,
        steps=steps,
    )
    save_run(persisted)
    loaded = load_run(run_id)
    verdict = loaded.steps[-1].precondition_verdict
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert loaded.steps[-1].site_health_alert is not None

    resumed = resume_modelo_workflow(run_id)
    assert resumed.resumed_from_run_id == run_id
    assert resumed.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE


def test_unhandled_recorder_persists_a_resumable_operator_decision() -> None:
    """The real unhandled recorder shares the operational resume outcome."""
    run_id = "8" * 16
    steps: list[WorkflowStep] = []

    with pytest.raises(WorkflowAbortSignalError) as raised:
        record_unhandled(
            stage=WorkflowStage.RUNNING_PREFLIGHT,
            started=_T,
            exc=RuntimeError("workflow preflight failed"),
            steps=steps,
        )

    assert raised.value.reason is WorkflowAbortReason.UNHANDLED_EXCEPTION
    persisted = _recorded_operational_result(
        run_id=run_id,
        reason=raised.value.reason,
        steps=steps,
    )
    save_run(persisted)
    loaded = load_run(run_id)
    verdict = loaded.steps[-1].precondition_verdict
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION

    resumed = resume_modelo_workflow(run_id)
    assert resumed.resumed_from_run_id == run_id
    assert resumed.aborted_reason is WorkflowAbortReason.UNHANDLED_EXCEPTION


def _done_result(run_id: str) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.LOADING_PROFILE,
        started_at=_T,
        ended_at=_T,
        success=True,
        summary_locale_key="application.workflow.steps.profile_loaded",
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        obligation=_obligation(),
        steps=(step,),
        summary_locale_key="application.workflow.results.completed",
    )


def _seed_current_revision(work_unit_id: str) -> str:
    repository = CalculationRevisionCatalogueRepository()
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_RESUME_CASILLA: "10"},
        binding_overrides={},
        casilla_values={_RESUME_CASILLA: Decimal("10")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={_RESUME_CASILLA: "10"},
        casilla_values={_RESUME_CASILLA: Decimal("10")},
        observations=(
            CasillaObservation(
                casilla_id=_RESUME_CASILLA,
                value=Decimal("10"),
                legal_refs=("ley-58-2003:art-93",),
                source_refs=("aeat-workflow-resume-test",),
            ),
        ),
        created_at=_T,
        updated_at=_T,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repository.save(upsert_calculation_revision(repository.load(), revision))
    work_repository = WorkUnitCatalogueRepository()
    work_unit = work_repository.load().get(work_unit_id)
    assert work_unit is not None
    work_repository.save(
        upsert_work_unit(
            work_repository.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": revision_id}),
        ),
    )
    return revision_id


def test_resume_returns_context_for_resumable_aborted_run(tmp_path: Path) -> None:
    run_id = "a" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation(),
        ),
    )
    context = resume_modelo_workflow(run_id)
    assert isinstance(context, WorkflowResumeContext)
    assert context.resumed_from_run_id == run_id
    assert context.modelo == "130"
    assert context.period == Period.from_year_and_code(2026, "1T")
    assert context.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
    assert context.obligation.modelo == "130"


def test_resume_refuses_done_run(tmp_path: Path) -> None:
    run_id = "b" * 16
    save_run(_done_result(run_id))
    with pytest.raises(WorkflowResumeRefusedError) as raised:
        resume_modelo_workflow(run_id)
    assert raised.value.translated_message == "application.workflow.errors.resume_refused_not_aborted"


def test_resume_refuses_non_resumable_reasons() -> None:
    cases = (
        ("c" * 16, WorkflowAbortReason.NO_PENDING_OBLIGATION),
        ("d" * 16, WorkflowAbortReason.ALREADY_FILED),
        ("e" * 16, WorkflowAbortReason.USER_CANCELLED),
    )

    for run_id, reason in cases:
        save_run(
            _aborted_result(
                run_id=run_id,
                reason=reason,
                obligation=_obligation() if reason is not WorkflowAbortReason.NO_PENDING_OBLIGATION else None,
            ),
        )
        with pytest.raises(WorkflowResumeRefusedError) as raised:
            resume_modelo_workflow(run_id)
        assert raised.value.translated_message == "application.workflow.errors.resume_refused_terminal_reason"


def test_resume_refuses_run_without_obligation(tmp_path: Path) -> None:
    run_id = "d" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=None,
        ),
    )
    with pytest.raises(WorkflowResumeRefusedError) as raised:
        resume_modelo_workflow(run_id)
    assert raised.value.translated_message == "application.workflow.errors.resume_refused_no_obligation"


def test_resume_for_missing_run_id_surfaces_workflow_error(tmp_path: Path) -> None:
    with pytest.raises(WorkflowError) as raised:
        resume_modelo_workflow("missing-run-id-9")
    assert raised.value.translated_message == "application.workflow.errors.run_not_found"


def test_resume_context_run_id_satisfies_engine_resumed_from_contract(tmp_path: Path) -> None:
    """The resume action returns a ``resumed_from_run_id`` that matches the
    engine's ``run_for_period(resumed_from=...)`` boundary contract: a
    16-character lowercase hex string.

    Locks the end-to-end shape of the resume → engine linkage so the
    two halves stay compatible without requiring the full live
    composite engine to run inside the resume unit suite.
    """

    run_id = "0" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation(),
        ),
    )
    context = resume_modelo_workflow(run_id)

    forwarded = context.resumed_from_run_id
    assert len(forwarded) == 16
    assert all(ch in "0123456789abcdef" for ch in forwarded)

    # A WorkflowResult constructed with the forwarded id round-trips
    # through the result-model validation that the engine emits at
    # the end of run_for_period — proves the producer/consumer contract.
    chained = WorkflowResult(
        run_id="b" * 16,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        obligation=_obligation(),
        steps=(
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=_T,
                ended_at=_T,
                success=True,
                summary_locale_key="application.workflow.steps.profile_loaded",
            ),
        ),
        summary_locale_key="application.workflow.results.completed",
        resumed_from=forwarded,
    )
    assert chained.resumed_from == run_id


def test_resume_for_unknown_run_id_is_indistinguishable_from_stale(tmp_path: Path) -> None:
    """A ``resumed_from`` run id that no longer resolves through the persistence
    layer surfaces as the same :class:`WorkflowError` the resume action raises
    for a never-saved run, locking the contract that stale and absent ids
    share one error path. The engine itself cannot verify existence; the
    upstream resume action is the gate."""

    with pytest.raises(WorkflowError) as raised:
        resume_modelo_workflow("c" * 16)
    assert raised.value.translated_message == "application.workflow.errors.run_not_found"


def test_resume_is_idempotent_for_a_persistently_aborted_run(tmp_path: Path) -> None:
    """Calling ``resume_modelo_workflow`` twice on the same aborted run
    returns equivalent contexts. The action is read-only over the prior
    record and does not mutate it, so repeated resume requests must
    produce the same ``(modelo, period, obligation, aborted_reason)``
    payload."""

    run_id = "f" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation(),
        ),
    )
    first = resume_modelo_workflow(run_id)
    second = resume_modelo_workflow(run_id)
    assert first == second
    assert first.resumed_from_run_id == second.resumed_from_run_id == run_id


def test_find_latest_run_for_period_returns_newest_match(tmp_path: Path) -> None:
    """``find_latest_run_for_period`` resolves the newest persisted run for
    a ``(modelo, period)`` pair, so an operator who only knows the
    work unit's modelo and period can discover the run id without
    holding the 16-character hash by hand."""

    earlier = _aborted_result(
        run_id="a" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", Period.from_year_and_code(2026, "1T")),
    ).model_copy(update={"started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC)})
    later = _aborted_result(
        run_id="b" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", Period.from_year_and_code(2026, "1T")),
    ).model_copy(update={"started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC)})
    save_run(earlier)
    save_run(later)

    resolved = find_latest_run_for_period(modelo="130", period=Period.from_year_and_code(2026, "1T"))
    assert resolved.run_id == later.run_id


def test_find_latest_run_for_period_ignores_other_periods(tmp_path: Path) -> None:
    """Only runs whose resolved obligation matches the requested
    ``(modelo, period)`` are considered."""

    save_run(
        _aborted_result(
            run_id="a" * 16,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation("303", Period.from_year_and_code(2026, "2T")),
        ),
    )
    with pytest.raises(WorkflowError) as raised:
        find_latest_run_for_period(modelo="130", period=Period.from_year_and_code(2026, "1T"))
    assert raised.value.translated_message == "application.workflow.errors.no_run_for_period"


def test_find_latest_run_for_period_resolves_id_for_resume(tmp_path: Path) -> None:
    """The run id resolved from a ``(modelo, period)`` pair feeds
    :func:`resume_modelo_workflow` directly — the discoverability
    path an operator holding only a work unit relies on."""

    run = _aborted_result(
        run_id="e" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", Period.from_year_and_code(2026, "1T")),
    )
    save_run(run)

    resolved = find_latest_run_for_period(modelo="130", period=Period.from_year_and_code(2026, "1T"))
    context = resume_modelo_workflow(resolved.run_id)
    assert context.resumed_from_run_id == run.run_id
    assert context.modelo == "130"
    assert context.period == Period.from_year_and_code(2026, "1T")


def test_find_unique_run_for_period_returns_single_match(tmp_path: Path) -> None:
    run = _aborted_result(
        run_id="a" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", Period.from_year_and_code(2026, "1T")),
    )
    save_run(run)

    resolved = find_unique_run_for_period(modelo="130", period=Period.from_year_and_code(2026, "1T"))

    assert resolved.run_id == run.run_id


def test_find_unique_run_for_period_refuses_multiple_matches_with_candidate_guidance(tmp_path: Path) -> None:
    earlier = _aborted_result(
        run_id="a" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", Period.from_year_and_code(2026, "1T")),
    ).model_copy(update={"started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC)})
    later = _aborted_result(
        run_id="b" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", Period.from_year_and_code(2026, "1T")),
    ).model_copy(update={"started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC)})
    save_run(earlier)
    save_run(later)

    with pytest.raises(WorkflowResumeRunAmbiguousError) as raised:
        find_unique_run_for_period(modelo="130", period=Period.from_year_and_code(2026, "1T"))

    assert raised.value.translated_message == "application.workflow.errors.resume_run_ambiguous"
    assert [candidate.run_id for candidate in raised.value.candidates] == [later.run_id, earlier.run_id]
    message = resolve_error_message(raised.value)
    assert "run_id\tmodelo\tperiod\tfinal_stage" in message
    assert later.run_id in message
    assert earlier.run_id in message


def test_visible_modelo_resume_target_resolves_single_workflow_run(tmp_path: Path) -> None:
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
    )
    workflow_period = workflow_period_for_work_unit(work_unit)
    run = _aborted_result(
        run_id="1" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    )
    save_run(run)

    resolved = resolve_modelo_visible_workflow_run_for_resume(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        bucket_id=_BUCKET_ID,
    )
    via_target = resolve_modelo_workflow_run_for_resume(
        ModeloVisibleFilingTarget(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            bucket_id=_BUCKET_ID,
        ),
        catalogue=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID).load(),
        bucket_id=_BUCKET_ID,
    )

    assert resolved.run_id == run.run_id
    assert via_target.run_id == run.run_id


def test_visible_modelo_resume_target_refuses_ambiguous_workflow_runs(tmp_path: Path) -> None:
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
    )
    workflow_period = workflow_period_for_work_unit(work_unit)
    earlier = _aborted_result(
        run_id="2" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    ).model_copy(update={"started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC)})
    later = _aborted_result(
        run_id="3" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    ).model_copy(update={"started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC)})
    save_run(earlier)
    save_run(later)

    with pytest.raises(WorkflowResumeRunAmbiguousError) as raised:
        resolve_modelo_visible_workflow_run_for_resume(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            bucket_id=_BUCKET_ID,
        )

    assert [candidate.run_id for candidate in raised.value.candidates] == [later.run_id, earlier.run_id]


def test_exact_modelo_work_target_resolves_latest_run_for_period(tmp_path: Path) -> None:
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
    )
    workflow_period = workflow_period_for_work_unit(work_unit)
    earlier = _aborted_result(
        run_id="4" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    ).model_copy(update={"started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC)})
    later = _aborted_result(
        run_id="5" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    ).model_copy(update={"started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC)})
    save_run(earlier)
    save_run(later)

    resolved = resolve_modelo_exact_workflow_run_for_resume(work_unit_id=work_unit.work_unit_id, bucket_id=_BUCKET_ID)
    via_target = resolve_modelo_workflow_run_for_resume(
        ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=_BUCKET_ID),
        catalogue=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID).load(),
        bucket_id=_BUCKET_ID,
    )

    assert resolved.run_id == later.run_id
    assert via_target.run_id == later.run_id


def test_unified_resume_target_resolves_visible_modelo_target_with_projection(tmp_path: Path) -> None:
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
    )
    workflow_period = workflow_period_for_work_unit(work_unit)
    run = _aborted_result(
        run_id="6" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    )
    save_run(run)

    resolved = resolve_modelo_workflow_resume_target(
        modelo="130",
        year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        bucket_id=_BUCKET_ID,
    )

    assert resolved.run_id == run.run_id
    assert resolved.source == "visible_target"
    assert resolved.work_unit_id == work_unit.work_unit_id
    assert resolved.short_work_unit_id == work_unit.work_unit_id[-12:]
    assert resolved.filing_year == 2026
    assert resolved.period == workflow_period


def test_unified_resume_target_resolves_work_unit_id_to_latest_run(tmp_path: Path) -> None:
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
    )
    workflow_period = workflow_period_for_work_unit(work_unit)
    save_run(
        _aborted_result(
            run_id="7" * 16,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation("130", workflow_period),
        ).model_copy(update={"started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC)}),
    )
    later = _aborted_result(
        run_id="8" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    ).model_copy(update={"started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC)})
    save_run(later)

    resolved = resolve_modelo_workflow_resume_target(target=work_unit.work_unit_id)

    assert resolved.run_id == later.run_id
    assert resolved.source == "work_unit_id"
    assert resolved.work_unit_id == work_unit.work_unit_id


def test_unified_resume_target_routes_revision_selector_through_modelo_addressing(tmp_path: Path) -> None:
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
    )
    calculation_revision_id = _seed_current_revision(work_unit.work_unit_id)
    workflow_period = workflow_period_for_work_unit(work_unit)
    run = _aborted_result(
        run_id="9" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    )
    save_run(run)

    resolved = resolve_modelo_workflow_resume_target(
        modelo="130",
        year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        bucket_id=_BUCKET_ID,
        selector=ModeloCalculationRevisionSelector.CURRENT,
    )

    assert resolved.run_id == run.run_id
    assert resolved.source == "visible_target_revision_selector"
    assert resolved.calculation_revision_id == calculation_revision_id
    assert resolved.short_calculation_revision_id == calculation_revision_id[-12:]


def test_unified_resume_target_refuses_ambiguous_visible_modelo_runs_with_work_guidance(tmp_path: Path) -> None:
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
    )
    workflow_period = workflow_period_for_work_unit(work_unit)
    earlier = _aborted_result(
        run_id="a" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    ).model_copy(update={"started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC)})
    later = _aborted_result(
        run_id="b" * 16,
        reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation("130", workflow_period),
    ).model_copy(update={"started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC)})
    save_run(earlier)
    save_run(later)

    with pytest.raises(WorkflowResumeRunAmbiguousError) as raised:
        resolve_modelo_workflow_resume_target(
            modelo="130",
            year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            bucket_id=_BUCKET_ID,
        )

    message = resolve_error_message(raised.value)
    assert work_unit.work_unit_id in message
    assert work_unit.work_unit_id[-12:] in message
