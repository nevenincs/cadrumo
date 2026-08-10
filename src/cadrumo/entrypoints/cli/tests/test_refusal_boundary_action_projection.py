"""Real text and JSON transport of typed root-guard refusals."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
import typer

from ....application.modelo import ModeloWorkflowGateError
from ....application.operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ....application.workflow import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
)
from ....core import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ....core.config import override_settings
from ....core.errors import ErrorCategory, get_error_exit_code
from ....tests.cli_runner import invoke_cached_cli, invoke_typer_app, semantic_cli_output
from ....tests.secure_sql import isolated_profile_storage_root
from .._common import CliPolicyRefusalProjection, attach_cli_policy_refusal_projection
from .._errors import CliRefusedBoundaryError, command_error_boundary

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _persisted_builder_refusal_result() -> WorkflowResult:
    """Build the persisted terminal shape emitted for a real builder refusal."""
    started = datetime(2026, 4, 12, 9, 0, tzinfo=UTC)
    terminal = WorkflowStep(
        stage=WorkflowStage.BUILDING_DRAFT,
        started_at=started,
        ended_at=started,
        success=False,
        summary_locale_key="application.workflow.steps.draft_build_failed",
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
        run_id="9" * 16,
        started_at=started,
        ended_at=started,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
        steps=(terminal,),
        summary_locale_key="application.workflow.results.aborted",
    )


def test_workflow_gate_refusal_projects_its_persisted_action_to_json() -> None:
    """The registered CLI boundary resolves the gate's exact terminal verdict."""
    workflow_app = typer.Typer()

    @workflow_app.command()
    @command_error_boundary
    def workflow_gate(json_out: bool = typer.Option(False, "--json")) -> None:
        del json_out
        raise ModeloWorkflowGateError(_persisted_builder_refusal_result())

    result = invoke_typer_app(workflow_app, ["--json"], catch_exceptions=False)

    assert result.exit_code == get_error_exit_code(ErrorCategory.REFUSED), result.output
    document = json.loads(result.stderr)
    action = document["error"]["action"]
    assert action["action"] == {
        "action_id": "operator.modelo.work.calculate",
        "target_command_key": "modelo.work.calculate",
        "cli_path": ["app", "modelo", "work", "calculate"],
    }
    assert action["conditionality"] == "requires_arguments"
    assert action["missing_argument_names"] == ["work_unit_id"]
    assert action["argument_bindings"][0]["status"] == "missing"


def test_real_root_refusal_projects_exact_leaf_and_action_to_json(tmp_path: Path) -> None:
    """The generic boundary keeps the guarded leaf and strict action DTO."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        result = invoke_cached_cli(
            ["--format", "json", "app", "ledger", "list"],
            catch_exceptions=False,
        )

    assert result.exit_code == get_error_exit_code(ErrorCategory.REFUSED), result.output
    assert result.stdout == ""
    document = json.loads(result.stderr)
    assert document["command"] == "ledger.list"
    error = document["error"]
    assert error["action"] == {
        "failed_condition_id": "profile.active.available",
        "evidence": [
            {
                "condition_id": "profile.active.available",
                "evidence_id": "profile.active.state",
                "provenance": "application_state",
                "values": {
                    "active_profile_present": False,
                    "registered_profile_count": 0,
                },
            },
        ],
        "action": {
            "action_id": "operator.profile.create",
            "target_command_key": "config.profile.create",
            "cli_path": ["config", "profile", "create"],
        },
        "argument_bindings": [
            {
                "argument_name": "profile_name",
                "status": "missing",
                "value": None,
                "source": None,
                "source_key": None,
                "source_evidence_id": None,
            },
        ],
        "missing_argument_names": ["profile_name"],
        "conditionality": "requires_arguments",
        "no_recovery_outcome": None,
    }
    assert "suggestion" not in error


def test_real_root_refusal_derives_text_from_the_same_action_projection(tmp_path: Path) -> None:
    """Text exposes schema identities and bindings without recovery prose."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        result = invoke_cached_cli(
            ["app", "ledger", "list"],
            catch_exceptions=False,
        )

    assert result.exit_code == get_error_exit_code(ErrorCategory.REFUSED), result.output
    output = semantic_cli_output(result)
    assert "  command: ledger.list" in output
    assert '  action.failed_condition_id: "profile.active.available"' in output
    assert '"evidence_id":"profile.active.state"' in output
    assert (
        '  action.action: {"action_id":"operator.profile.create","cli_path":["config","profile","create"],'
        '"target_command_key":"config.profile.create"}'
    ) in output
    assert '"argument_name":"profile_name"' in output
    assert '  action.missing_argument_names: ["profile_name"]' in output
    assert '  action.conditionality: "requires_arguments"' in output
    assert "  action.no_recovery_outcome: null" in output
    assert "suggestion:" not in output


def test_real_root_no_recovery_refusal_projects_the_closed_outcome(tmp_path: Path) -> None:
    """A guarded terminal decision stays explicit rather than losing its leaf."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
            cadrumo_active_profile=None,
        ),
    ):
        result = invoke_cached_cli(
            ["--format", "json", "config", "google", "login"],
            catch_exceptions=False,
        )

    assert result.exit_code == get_error_exit_code(ErrorCategory.REFUSED), result.output
    document = json.loads(result.stderr)
    assert document["command"] == "config.google.login"
    action = document["error"]["action"]
    assert action["failed_condition_id"] == "storage.route.active_bucket"
    assert action["action"] is None
    assert action["argument_bindings"] == []
    assert action["missing_argument_names"] == []
    assert action["conditionality"] == "not_applicable"
    assert action["no_recovery_outcome"] == "operator_decision"


def test_boundary_fails_closed_on_a_malformed_typed_projection_marker() -> None:
    """A corrupt S17 handoff cannot degrade to an identity-less refusal."""

    @command_error_boundary
    def guarded_callback() -> None:
        refusal = CliRefusedBoundaryError("guard refused")
        raise attach_cli_policy_refusal_projection(
            refusal,
            projection=cast(CliPolicyRefusalProjection, object()),
        )

    with pytest.raises(TypeError, match="invalid typed projection"):
        guarded_callback()


def test_boundary_keeps_unmigrated_untyped_refusals_working(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """S18 does not globally reject refusal producers owned by later waves."""

    @command_error_boundary
    def untyped_refusal_callback() -> None:
        raise CliRefusedBoundaryError("untyped refusal")

    with pytest.raises(typer.Exit) as raised:
        untyped_refusal_callback()

    assert raised.value.exit_code == get_error_exit_code(ErrorCategory.REFUSED)
    assert "Refused. untyped refusal" in capsys.readouterr().err
