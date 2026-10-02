"""CLI surface tests for `aeat app modelo work resume` target resolution."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from contextvars import ContextVar
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.workflow_gate import workflow_period_for_work_unit
from ....application.operator_actions.models import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....application.workflow.abort import WorkflowAbortReason
from ....application.workflow.persistence import list_runs, load_run, save_run
from ....application.workflow.run_models import (
    WorkflowFailureDetails,
    WorkflowObligationFacts,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
)
from ....core.config import override_settings
from ....core.modelo import Modelo
from ....core.operator_action_enums import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ....core.period import Period
from ....domain.buckets.event import BucketEventObjectType, BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.models import ObligationStatus
from ...adapter_composition import build_work_lifecycle_ports
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_NATIVE_FIXTURE: ContextVar[NativeCliProfileFixture] = ContextVar("resume_native_fixture")
_AUTHORITY_PIN: ContextVar[PinnedAuthorityOperation] = ContextVar("resume_authority_pin")


def _invoke_work(args: Sequence[str], *, format: str | None = None, language: str | None = None) -> Result:
    fixture = _NATIVE_FIXTURE.get()
    assert fixture.label is not None
    close_active_bucket_session()
    prefix = ["--profile", fixture.label, "--profile-secrets-stdin"]
    if format is not None:
        prefix[:0] = ["--format", format]
    if language is not None:
        prefix[:0] = ["--language", language]
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            [*prefix, "app", "modelo", "work", *args],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


_T = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
_PROFILE_LABEL = "Native resume operator"


def _profile_facts() -> dict[str, str]:
    return {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Native",
        "identity.surnames": "Resume",
        "activities.description": "consulting",
        "censo.activity_start_date": "2025-01-01",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, authority_operation: PinnedAuthorityOperation) -> Iterator[None]:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label=_PROFILE_LABEL, facts=_profile_facts())
        close_active_bucket_session()
        login_profile(
            name=_PROFILE_LABEL,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        fixture_token = _NATIVE_FIXTURE.set(fixture)
        pin_token = _AUTHORITY_PIN.set(authority_operation)
        try:
            yield
        finally:
            _AUTHORITY_PIN.reset(pin_token)
            _NATIVE_FIXTURE.reset(fixture_token)


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
    bucket_id = resolve_login_target(_PROFILE_LABEL).bucket_id
    return create_work_unit(
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        operation=_AUTHORITY_PIN.get(),
    )


def _reopen_oracle_session() -> None:
    fixture = _NATIVE_FIXTURE.get()
    close_active_bucket_session()
    login_profile(
        name=_PROFILE_LABEL,
        passphrase_callback=lambda: fixture.passphrase,
        profile_decode_context=_AUTHORITY_PIN.get().profile_decode_context(),
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
    result = _invoke_work(["resume", run_id], language="en")
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

    json_result = _invoke_work(["runs"], format="json")
    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_result.output)["result"]
    rendered = next(row for row in payload["runs"] if row["run_id"] == run.run_id)
    assert rendered["final_stage"] == WorkflowStage.ABORTED.value
    assert rendered["aborted_reason"] == WorkflowAbortReason.DRAFT_HAS_ERRORS.value
    assert rendered["summary"]
    assert "summary_details" not in rendered
    assert "obligation" not in rendered
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

    run_result = _invoke_work(["run", run.run_id], format="json")
    assert run_result.exit_code == 0, run_result.output
    full = json.loads(run_result.output)["result"]
    assert full["run_id"] == run.run_id
    details_result = _invoke_work(["run-details", run.run_id], format="json")
    assert details_result.exit_code == 0, details_result.output
    details = json.loads(details_result.output)["result"]
    assert details["summary_detail_kind"] == "workflow_failure"
    assert details["summary_detail_facts"] == {"error_code": "workflow.draft.build_failure"}
    assert full["modelo"] == "130"
    assert full["obligation_status"] == "UPCOMING"

    _reopen_oracle_session()
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


def test_resume_accepts_exact_run_with_matching_expected_period() -> None:
    """An explicit year/period constrains the same recorded run's obligation."""
    run_id = "9" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE))
    result = _invoke_work(["resume", run_id, "--year", "2026", "--period", "1T"])
    assert result.exit_code == 0, result.output
    assert f"prior_workflow_run_id\t{run_id}" in result.output
    assert "period\t2026 1T" in result.output


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
    """Resume leaves domain events and the persisted run unchanged."""
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository

    run_id = "d" * 16
    run = _aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE)
    save_run(run)
    profile_id = resolve_login_target(_PROFILE_LABEL).bucket_id

    repo = BucketEventHistoryRepository()
    before = repo.load().events

    result = _invoke_work(["resume", run_id])

    _reopen_oracle_session()
    after = repo.load().events
    assert result.exit_code == 0
    assert all(after.get(event_id) == event for event_id, event in before.items())
    added = tuple(event for event_id, event in after.items() if event_id not in before)
    assert all(
        event.event_type is BucketEventType.PROFILE_ACTIVATED
        and event.object_type is BucketEventObjectType.PROFILE
        and event.actor == "profile-login"
        and event.object_id == profile_id
        for event in added
    ), tuple((event.event_type.value, event.object_type.value) for event in added)
    assert load_run(run_id) == run
