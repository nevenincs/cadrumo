"""Real text and JSON transport of typed root-guard refusals."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
import typer
from pydantic import TypeAdapter

from ....application.auth.acquisition_lock import acquire_auth_acquisition_lock
from ....application.modelo import ModeloWorkflowGateError
from ....application.operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from cadrumo.application.workflow.abort import WorkflowAbortReason
from cadrumo.application.workflow.run_models import WorkflowResult, WorkflowStage, WorkflowStep
from ....core import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    AuthProviderKind,
    MissingOptionalExtraError,
    OptionalExtra,
)
from ....core.config import Settings, override_settings
from ....core.errors import CoreValidationError, ErrorCategory, get_error_exit_code
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ....llm import LLMRequest, PromptDefinition
from ....tests.cli_runner import invoke_cached_cli, invoke_typer_app, semantic_cli_output
from ....tests.secure_sql import isolated_profile_storage_root
from .._common import CliPolicyRefusalProjection, attach_cli_policy_refusal_projection
from ..errors import CliRefusedBoundaryError, command_error_boundary
from ._english_locale_fixture import english_locale_fixture

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


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


def test_corrupt_active_profile_pointer_projects_the_canonical_repair_action(tmp_path: Path) -> None:
    """The core error contributes facts only; application policy resolves the repair action."""
    pointer_file = tmp_path / "active-profile"
    pointer_file.write_text("not = valid = toml", encoding="utf-8")
    pointer_app = typer.Typer()

    @pointer_app.command()
    @command_error_boundary
    def inspect_pointer(json_out: bool = typer.Option(False, "--json")) -> None:
        del json_out
        Settings(cadrumo_local_storage_root=tmp_path)

    result = invoke_typer_app(pointer_app, ["--json"], catch_exceptions=False)

    assert result.exit_code == get_error_exit_code(ErrorCategory.INTEGRITY), result.output
    error = json.loads(result.stderr)["error"]
    assert error["context"] == {
        "path": str(pointer_file),
        "pointer_corrupt": "true",
        "root_fallback_refused": "true",
    }
    assert error["action"] == {
        "failed_condition_id": "profile.active.pointer.valid",
        "evidence": [
            {
                "condition_id": "profile.active.pointer.valid",
                "evidence_id": "profile.active.pointer.corruption",
                "provenance": "runtime_observation",
                "values": {
                    "path": str(pointer_file),
                    "pointer_corrupt": True,
                    "root_fallback_refused": True,
                },
            },
        ],
        "action": {
            "action_id": "operator.profile.repair_active_pointer",
            "target_command_key": "config.repair.profile",
            "cli_path": ["config", "repair", "profile"],
        },
        "argument_bindings": [
            {
                "argument_name": "clear_active",
                "status": "resolved",
                "value": True,
                "source": "operator_action.verdict_context",
                "source_key": "clear_active",
                "source_evidence_id": None,
            },
            {
                "argument_name": "yes",
                "status": "missing",
                "value": None,
                "source": None,
                "source_key": None,
                "source_evidence_id": None,
            },
        ],
        "missing_argument_names": ["yes"],
        "conditionality": "requires_arguments",
        "no_recovery_outcome": None,
    }


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_nested_llm_request_validation_projects_its_terminal_verdict(locale: str) -> None:
    """The public callback boundary preserves a validator-owned refusal."""
    validation_app = typer.Typer()

    @validation_app.command()
    @command_error_boundary
    def validate_request(json_out: bool = typer.Option(False, "--json")) -> None:
        del json_out
        LLMRequest(prompt=" \t")

    result = invoke_typer_app(
        validation_app, ["--json"], catch_exceptions=False, env={"CADRUMO_OUTPUT_LANGUAGE": locale}
    )

    assert result.exit_code == get_error_exit_code(ErrorCategory.REFUSED), result.output
    document = json.loads(result.stderr)
    error = document["error"]
    assert error["code"] == "REFUSED_CLI_VALIDATION_BOUNDARY"
    action = error["action"]
    assert action["failed_condition_id"] == "llm.request.prompt_nonempty"
    assert action["evidence"] == [
        {
            "condition_id": "llm.request.prompt_nonempty",
            "evidence_id": "llm.request.prompt_nonempty.observation",
            "provenance": "application_state",
            "values": {"request_prompt_nonempty": False},
        },
    ]
    assert action["action"] is None
    assert action["conditionality"] == "not_applicable"
    assert action["no_recovery_outcome"] == "operator_decision"


@pytest.mark.parametrize(
    "validate",
    [
        lambda: LLMRequest.model_validate({"prompt": "valid", "max_tokens": 0}),
        lambda: TypeAdapter(tuple[LLMRequest, PromptDefinition]).validate_python(
            (
                {"prompt": " \t"},
                {"id": "Not canonical", "version": 1, "template": "{{ value }}", "description": "x"},
            ),
        ),
    ],
)
def test_nested_validation_fails_closed_without_one_typed_verdict(validate: Callable[[], object]) -> None:
    """No typed candidate and multiple typed candidates retain the generic outcome."""
    validation_app = typer.Typer()

    @validation_app.command()
    @command_error_boundary
    def validate_request(json_out: bool = typer.Option(False, "--json")) -> None:
        del json_out
        validate()

    result = invoke_typer_app(validation_app, ["--json"], catch_exceptions=False)

    assert result.exit_code == get_error_exit_code(ErrorCategory.REFUSED), result.output
    action = json.loads(result.stderr)["error"]["action"]
    assert action["failed_condition_id"] == "cli.validation.boundary_clean"
    assert action["evidence"][0]["values"] == {"boundary_error_type": "CliValidationBoundaryError"}
    assert action["action"] is None
    assert action["conditionality"] == "not_applicable"
    assert action["no_recovery_outcome"] == "operator_decision"


@pytest.mark.parametrize(
    ("error", "condition", "facts"),
    [
        (
            MissingOptionalExtraError(OptionalExtra(extra="proof", import_name="absent.proof", feature="proof")),
            "provisioning.optional_extra.importable",
            {"extra": "proof", "import_name": "absent.proof", "importable": False},
        ),
        (
            CoreValidationError(context={"section": "aeat.pre303", "validation_error": "withheld"}),
            "cli.external_constants.section_valid",
            {"section": "aeat.pre303", "valid": False},
        ),
    ],
)
@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_shared_boundary_maps_declared_s114_producers(
    error: CoreValidationError | MissingOptionalExtraError,
    condition: str,
    facts: dict[str, str | bool],
    locale: str,
) -> None:
    """Refusal producer families emit machine facts without their raw prose."""
    producer_app = typer.Typer()

    @producer_app.command()
    @command_error_boundary
    def refuse(json_out: bool = typer.Option(False, "--json")) -> None:
        del json_out
        raise error

    result = invoke_typer_app(
        producer_app,
        ["--json"],
        catch_exceptions=False,
        env={"CADRUMO_OUTPUT_LANGUAGE": locale},
    )

    envelope = json.loads(result.stderr)["error"]
    action = envelope["action"]
    assert action["failed_condition_id"] == condition
    assert action["evidence"][0]["values"] == facts
    assert action["action"] is None
    assert action["conditionality"] == "not_applicable"
    assert action["no_recovery_outcome"] == "operator_decision"
    if isinstance(error, MissingOptionalExtraError):
        assert envelope["context"] == {"extra": "proof", "import_name": "absent.proof", "importable": "false"}
        assert "feature" not in envelope["context"]
        assert "install_hint" not in envelope["context"]
        assert "pip install" not in result.stderr
    else:
        assert envelope["context"] == {"section": "aeat.pre303", "validation_error_type": "ValidationError"}
        assert "validation_error" not in envelope["context"]
        assert "withheld" not in result.stderr


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


def test_auth_acquisition_conflict_projects_factual_no_recovery_to_json(tmp_path: Path) -> None:
    """A real held auth lock reaches the CLI only through its typed verdict."""
    auth_app = typer.Typer()
    settings = Settings(cadrumo_token_dir=tmp_path / "tokens")

    @auth_app.command()
    @command_error_boundary
    def acquire(json_out: bool = typer.Option(False, "--json")) -> None:
        del json_out
        with (
            acquire_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, ttl_seconds=60),
            acquire_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, ttl_seconds=60),
        ):
            pass

    with override_settings(cadrumo_active_profile="operator"):
        result = invoke_typer_app(auth_app, ["--json"], catch_exceptions=False)

    assert result.exit_code == get_error_exit_code(ErrorCategory.LOCKED), result.output
    document = json.loads(result.stderr)
    action = document["error"]["action"]
    assert action == {
        "failed_condition_id": "auth.acquisition_lock.available",
        "evidence": [
            {
                "condition_id": "auth.acquisition_lock.available",
                "evidence_id": "auth.acquisition_lock.state",
                "provenance": "application_state",
                "values": {
                    "lock_available": False,
                    "lock_recoverable": False,
                    "lock_state": "held",
                },
            },
        ],
        "action": None,
        "argument_bindings": [],
        "missing_argument_names": [],
        "conditionality": "not_applicable",
        "no_recovery_outcome": "operator_decision",
    }
    assert "suggestion" not in document["error"]


def test_boundary_fails_closed_on_a_malformed_typed_projection_marker() -> None:
    """A corrupt boundary handoff cannot degrade to an identity-less refusal."""

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
    """The projection does not globally reject refusal producers it does not own."""

    @command_error_boundary
    def untyped_refusal_callback() -> None:
        raise CliRefusedBoundaryError("untyped refusal")

    with pytest.raises(typer.Exit) as raised:
        untyped_refusal_callback()

    assert raised.value.exit_code == get_error_exit_code(ErrorCategory.REFUSED)
    assert "Refused. untyped refusal" in capsys.readouterr().err
