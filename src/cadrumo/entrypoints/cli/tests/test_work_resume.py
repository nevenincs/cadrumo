"""CLI surface tests for `aeat app modelo work resume` target resolution."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from click.testing import Result

from ....application.modelo import create_work_unit, workflow_period_for_work_unit
from ....application.operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ....application.workflow import (
    WorkflowAbortReason,
    WorkflowFailureDetails,
    WorkflowObligationFacts,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    list_runs,
    load_run,
    save_run,
)
from ....core import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    Modelo,
    NoRecoveryOutcome,
    Period,
    resolve_active_bucket_id,
)
from ....domain.deadlines import ObligationStatus
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session, seed_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_work(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "modelo", "work", *args])


_T = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_PROFILE_LABEL = "resume-test"
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Operator"),
    UserProfileFact(path="identity.surnames", value="Resume"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
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
        label=_PROFILE_LABEL,
    )


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_PROFILE_ID),
    ):
        register_minimal_profile(profile_id=_PROFILE_ID, display_name=_PROFILE_LABEL)
        _seed_ready_profile_record(_PROFILE_ID)
        yield


def _obligation(modelo: str = "130", period: Period | None = None) -> WorkflowObligationFacts:
    target_period = period or Period.from_year_and_code(2026, "1T")
    return WorkflowObligationFacts(
        modelo=Modelo(modelo),
        period=target_period,
        opens_on=date(2026, 4, 1),
        closes_on=date(2026, 4, 20),
        status=ObligationStatus.UPCOMING,
    )


def _aborted_run(run_id: str, *, reason: WorkflowAbortReason) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.BUILDING_DRAFT,
        started_at=_T,
        ended_at=_T,
        success=False,
        summary_locale_key="application.workflow.steps.site_unavailable",
        details=WorkflowFailureDetails(
            kind="workflow_failure",
            error_code="workflow.site.unavailable",
        ),
        precondition_verdict=PreconditionVerdict(
            failed_condition_id="workflow.site.available",
            evidence=(
                ConditionEvidence(
                    condition_id="workflow.site.available",
                    evidence_id="workflow.site.health",
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                    values={"site_available": False},
                ),
            ),
            conditionality=ActionConditionality.NOT_APPLICABLE,
            no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=reason,
        obligation=_obligation(),
        steps=(step,),
        summary_locale_key="application.workflow.results.aborted",
        summary_details=step.details,
    )


def _done_run(run_id: str) -> WorkflowResult:
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


def _builder_refused_run(run_id: str) -> WorkflowResult:
    """Build the persisted shape the real builder-refusal producer records."""
    step = WorkflowStep(
        stage=WorkflowStage.BUILDING_DRAFT,
        started_at=_T,
        ended_at=_T,
        success=False,
        summary_locale_key="application.workflow.steps.draft_build_failed",
        details=WorkflowFailureDetails(
            kind="workflow_failure",
            error_code="workflow.draft.build_failure",
        ),
        precondition_verdict=PreconditionVerdict(
            failed_condition_id="workflow.draft.buildable",
            evidence=(
                ConditionEvidence(
                    condition_id="workflow.draft.buildable",
                    evidence_id="workflow.draft.build_failure",
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                    values={"buildable": False},
                ),
            ),
            action=ActionReference(action_id="operator.modelo.work.calculate"),
            argument_bindings=(
                ActionArgumentBinding(
                    argument_name="work_unit_id",
                    status=ActionArgumentStatus.MISSING,
                ),
            ),
            missing_argument_names=("work_unit_id",),
            conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
        ),
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
        obligation=_obligation(),
        steps=(step,),
        summary_locale_key="application.workflow.results.aborted",
        summary_details=step.details,
    )


def _seed_work_unit():
    bucket_id = resolve_active_bucket_id()
    assert isinstance(bucket_id, str)
    return create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
    )


def test_resume_help_advertises_the_command() -> None:
    result = _invoke_work(["resume", "--help"])
    assert result.exit_code == 0
    # Optional positional metavar, Typer-rendered as `[target]` (older Typer
    # used bare-uppercase `TARGET`); the positional is still advertised.
    assert "[target]" in result.output
    assert "--modelo" in result.output
    assert "--year" in result.output
    assert "--period" in result.output
    assert "AEAT" in result.output  # the docstring mentions the non-contact guarantee


def test_resume_surfaces_obligation_for_resumable_run() -> None:
    run_id = "a" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE))
    result = _invoke_work(["resume", run_id])
    assert result.exit_code == 0, result.output
    assert "modelo\t130" in result.output
    assert "period\t2026 1T" in result.output
    assert "registry_period\t1T" in result.output
    assert "aborted_reason\tSITE_UNAVAILABLE" in result.output


def test_resume_refuses_done_run_with_bad_parameter() -> None:
    run_id = "b" * 16
    save_run(_done_run(run_id))
    result = _invoke_work(["resume", run_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_resume_refuses_missing_run_with_bad_parameter() -> None:
    result = _invoke_work(["resume", "0" * 16])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_resume_refuses_non_resumable_reason() -> None:
    run_id = "c" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.USER_CANCELLED))
    result = _invoke_work(["resume", run_id])
    assert result.exit_code != 0
    assert "terminal by design" in result.output


def test_runs_lists_persisted_run_ids() -> None:
    """`work runs` lists persisted runs with their run ids so an
    operator can discover the 16-character id `work resume` needs."""

    save_run(_aborted_run("a" * 16, reason=WorkflowAbortReason.SITE_UNAVAILABLE))
    save_run(_done_run("b" * 16))

    result = _invoke_work(["runs"])
    assert result.exit_code == 0, result.output
    assert "run_count\t2" in result.output
    assert "a" * 16 in result.output
    assert "b" * 16 in result.output
    assert "130\t2026 1T" in result.output


def test_work_runs_projects_a_typed_builder_refusal_without_reconstructing_a_command() -> None:
    """The real CLI renders persisted facts and no longer carries a string recovery channel."""
    run = _builder_refused_run("f" * 16)
    save_run(run)

    stored_before = load_run(run.run_id)
    assert stored_before == run
    terminal = stored_before.steps[-1]
    assert terminal.summary_locale_key == "application.workflow.steps.draft_build_failed"
    assert terminal.details == WorkflowFailureDetails(
        kind="workflow_failure",
        error_code="workflow.draft.build_failure",
    )
    assert terminal.precondition_verdict is not None
    assert terminal.precondition_verdict.action is not None
    assert terminal.precondition_verdict.action.action_id == "operator.modelo.work.calculate"
    assert terminal.precondition_verdict.missing_argument_names == ("work_unit_id",)

    text_result = _invoke_work(["runs"])
    assert text_result.exit_code == 0, text_result.output
    assert "run_id\tmodelo\tperiod\tfinal_stage\taborted_reason\tstarted_at\tsummary\taction" in text_result.output
    assert "next_action" not in text_result.output
    assert "aeat app modelo work calculate" not in text_result.output
    assert "application.workflow.steps.draft_build_failed" not in text_result.output
    assert '"action_id":"operator.modelo.work.calculate"' in text_result.output
    assert '"missing_argument_names":["work_unit_id"]' in text_result.output
    assert '"conditionality":"requires_arguments"' in text_result.output

    json_result = invoke_cached_cli(["--format", "json", "app", "modelo", "work", "runs"])
    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_result.output)["result"]
    rendered = next(row for row in payload["runs"] if row["run_id"] == run.run_id)
    assert rendered["final_stage"] == WorkflowStage.ABORTED.value
    assert rendered["aborted_reason"] == WorkflowAbortReason.DRAFT_HAS_ERRORS.value
    assert rendered["summary"]
    assert "next_action" not in rendered
    assert rendered["action"] == {
        "failed_condition_id": "workflow.draft.buildable",
        "evidence": [
            {
                "condition_id": "workflow.draft.buildable",
                "evidence_id": "workflow.draft.build_failure",
                "provenance": "application_state",
                "values": {"buildable": False},
            },
        ],
        "action": {
            "action_id": "operator.modelo.work.calculate",
            "target_command_key": "modelo.work.calculate",
            "cli_path": ["app", "modelo", "work", "calculate"],
        },
        "argument_bindings": [
            {
                "argument_name": "work_unit_id",
                "status": "missing",
                "value": None,
                "source": None,
                "source_key": None,
                "source_evidence_id": None,
            },
        ],
        "missing_argument_names": ["work_unit_id"],
        "conditionality": "requires_arguments",
        "no_recovery_outcome": None,
    }

    assert load_run(run.run_id) == stored_before
    assert [candidate.run_id for candidate in list_runs()] == [run.run_id]


def test_resume_rejects_a_malformed_target() -> None:
    """A target that is neither a 16-character run id nor a
    64-character work-unit id is refused with operator guidance."""

    result = _invoke_work(["resume", "not-an-id"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "work runs" in result.output


def test_resume_accepts_run_id_directly() -> None:
    """A 16-character run id passed directly resolves to that run."""

    run_id = "e" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE))
    result = _invoke_work(["resume", run_id])
    assert result.exit_code == 0, result.output
    assert f"prior_workflow_run_id\t{run_id}" in result.output


def test_resume_accepts_modelo_year_period_without_raw_id() -> None:
    work_unit = _seed_work_unit()
    workflow_period = workflow_period_for_work_unit(work_unit)
    run_id = "f" * 16
    save_run(
        _aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE).model_copy(
            update={"obligation": _obligation("130", workflow_period)},
        ),
    )

    result = _invoke_work(["resume", "--modelo", "130", "--year", "2026", "--period", "1T"])

    assert result.exit_code == 0, result.output
    assert f"prior_workflow_run_id\t{run_id}" in result.output
    assert "resolved_source\tvisible_target" in result.output
    assert f"work_unit_id\t{work_unit.work_unit_id}" in result.output


def test_resume_accepts_exact_work_unit_id() -> None:
    work_unit = _seed_work_unit()
    workflow_period = workflow_period_for_work_unit(work_unit)
    earlier = _aborted_run("1" * 16, reason=WorkflowAbortReason.SITE_UNAVAILABLE).model_copy(
        update={
            "obligation": _obligation("130", workflow_period),
            "started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC),
        },
    )
    later = _aborted_run("2" * 16, reason=WorkflowAbortReason.SITE_UNAVAILABLE).model_copy(
        update={
            "obligation": _obligation("130", workflow_period),
            "started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC),
        },
    )
    save_run(earlier)
    save_run(later)

    result = _invoke_work(["resume", work_unit.work_unit_id])

    assert result.exit_code == 0, result.output
    assert "prior_workflow_run_id\t2222222222222222" in result.output
    assert "resolved_source\twork_unit_id" in result.output


def test_resume_refuses_ambiguous_modelo_year_period_with_candidate_guidance() -> None:
    work_unit = _seed_work_unit()
    workflow_period = workflow_period_for_work_unit(work_unit)
    save_run(
        _aborted_run("3" * 16, reason=WorkflowAbortReason.SITE_UNAVAILABLE).model_copy(
            update={
                "obligation": _obligation("130", workflow_period),
                "started_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC),
            },
        ),
    )
    save_run(
        _aborted_run("4" * 16, reason=WorkflowAbortReason.SITE_UNAVAILABLE).model_copy(
            update={
                "obligation": _obligation("130", workflow_period),
                "started_at": datetime(2026, 4, 12, 9, 0, tzinfo=UTC),
            },
        ),
    )

    result = _invoke_work(["resume", "--modelo", "130", "--year", "2026", "--period", "1T"])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert work_unit.work_unit_id in result.output


def test_resume_emits_no_bucket_event() -> None:
    """The resume verb must not emit any bucket event into BucketEventHistoryRepository.

    Drives `work resume` against a real persisted aborted run through the CLI
    runner and asserts that the real BucketEventHistoryRepository (backed by
    the isolated SQLite engine) has zero entries after the command completes.
    """
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository

    run_id = "d" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE))

    repo = BucketEventHistoryRepository()
    before = repo.load().events

    result = _invoke_work(["resume", run_id])

    after = repo.load().events
    new_event_ids = set(after.keys()) - set(before.keys())
    assert not new_event_ids, (
        f"`work resume` emitted {len(new_event_ids)} unexpected bucket event(s): "
        f"{new_event_ids!r}. The resume verb must be read-only. "
        f"CLI output:\n{result.output}"
    )
