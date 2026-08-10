"""Locale-neutral workflow-run action and presentation integration tests."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.browser import SiteHealthState
from ....application.operator_actions import (
    ActionArgumentBinding,
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionReference,
    ConditionEvidence,
    ConditionEvidenceProvenance,
    NoRecoveryOutcome,
    PreconditionVerdict,
)
from ....application.user_profile import UserProfileLifecycleRepository, profile_create_storage_span
from ....application.workflow import (
    SiteHealthAlert,
    WorkflowAbortReason,
    WorkflowFailureDetails,
    WorkflowObligationFacts,
    WorkflowResult,
    WorkflowSiteHealthFacts,
    WorkflowStage,
    WorkflowStep,
    save_run,
    workflow_state_repository,
)
from ....core import Modelo, Period
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ....domain.deadlines import ObligationStatus
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .._common import resolve_cli_precondition_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_T = datetime(2026, 4, 12, 9, 0, tzinfo=UTC)
_PROFILE_ID = "22222222-2222-4222-8222-222222222222"
_PROFILE_LABEL = "work-runs-locales"
_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Operator"),
    UserProfileFact(path="identity.surnames", value="Workflow"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)
_RAW_COMMAND_PATTERN = re.compile(r"(?i)(?:^|[\s`'\"])(?:aeat)\s+")


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=_PROFILE_ID,
                display_name=_PROFILE_LABEL,
            ),
        )
        UserProfileLifecycleRepository(bucket_id=_PROFILE_ID).save(
            UserProfileRecord(
                profile_id=_PROFILE_ID,
                display_name=_PROFILE_LABEL,
                facts=_PROFILE_FACTS,
                created_at=_T,
                updated_at=_T,
            ),
        )
        yield


def _obligation() -> WorkflowObligationFacts:
    return WorkflowObligationFacts(
        modelo=Modelo("130"),
        period=Period.from_year_and_code(2026, "1T"),
        opens_on=date(2026, 4, 1),
        closes_on=date(2026, 4, 20),
        status=ObligationStatus.UPCOMING,
    )


def _actionable_run() -> WorkflowResult:
    verdict = PreconditionVerdict(
        failed_condition_id="workflow.draft.buildable",
        evidence=(
            ConditionEvidence(
                condition_id="workflow.draft.buildable",
                evidence_id="workflow.draft.build_failure",
                provenance=ConditionEvidenceProvenance.APPLICATION_STATE,
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
    )
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
        precondition_verdict=verdict,
    )
    return WorkflowResult(
        run_id="7" * 16,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
        obligation=_obligation(),
        steps=(step,),
        summary_locale_key="application.workflow.results.aborted",
        summary_details=step.details,
    )


def _site_health_run() -> WorkflowResult:
    verdict = PreconditionVerdict(
        failed_condition_id="workflow.site.available",
        evidence=(
            ConditionEvidence(
                condition_id="workflow.site.available",
                evidence_id="workflow.site.health",
                provenance=ConditionEvidenceProvenance.RUNTIME_OBSERVATION,
                values={"site_available": False},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    step = WorkflowStep(
        stage=WorkflowStage.RUNNING_PREFLIGHT,
        started_at=_T,
        ended_at=_T,
        success=False,
        summary_locale_key="application.workflow.steps.site_unavailable",
        details=WorkflowFailureDetails(
            kind="workflow_failure",
            error_code="workflow.site.unavailable",
        ),
        precondition_verdict=verdict,
        site_health_alert=SiteHealthAlert(
            stage=WorkflowStage.RUNNING_PREFLIGHT,
            status=WorkflowSiteHealthFacts(
                alert_code="workflow.site.mantenimiento",
                state=SiteHealthState.MANTENIMIENTO,
                observed_at=_T,
                http_status=503,
                retry_after_seconds=120,
                detected_marker_count=2,
            ),
            run_id="8" * 16,
        ),
    )
    return WorkflowResult(
        run_id="8" * 16,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        obligation=_obligation(),
        steps=(step,),
        summary_locale_key="application.workflow.results.aborted",
        summary_details=step.details,
    )


def test_work_runs_localizes_only_human_text_and_keeps_one_structural_envelope() -> None:
    """Four real CLI locales share one typed graph and vary only human summaries."""
    action_run = _actionable_run()
    health_run = _site_health_run()
    save_run(action_run)
    save_run(health_run)

    summaries_by_locale: dict[str, tuple[str, str]] = {}
    structural_digests: set[str] = set()
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "runs",
                "--output-language",
                language,
            ],
        )
        assert result.exit_code == 0, result.output
        rows = {row["run_id"]: row for row in json.loads(result.output)["result"]["runs"]}
        action_row = rows[action_run.run_id]
        health_row = rows[health_run.run_id]
        summaries_by_locale[language] = (action_row["summary"], health_row["summary"])

        assert action_row["summary_locale_key"] == "application.workflow.steps.draft_build_failed"
        assert action_row["summary_details"] == {
            "kind": "workflow_failure",
            "error_code": "workflow.draft.build_failure",
        }
        assert action_row["obligation"]["modelo"] == "130"
        assert action_row["summary_stage"] == WorkflowStage.BUILDING_DRAFT.value
        assert action_row["site_health_alert"] is None
        assert action_row["action"]["action"] == {
            "action_id": "operator.modelo.work.calculate",
            "target_command_key": "modelo.work.calculate",
            "cli_path": ["app", "modelo", "work", "calculate"],
        }
        assert action_row["action"]["missing_argument_names"] == ["work_unit_id"]
        assert health_row["action"]["action"] is None
        assert health_row["action"]["no_recovery_outcome"] == "operator_decision"
        assert health_row["site_health_alert"]["status"] == {
            "alert_code": "workflow.site.mantenimiento",
            "state": "mantenimiento",
            "observed_at": _T.isoformat(),
            "http_status": 503,
            "retry_after_seconds": 120,
            "detected_marker_count": 2,
        }

        structural_rows = []
        for row in rows.values():
            structural = dict(row)
            structural.pop("summary")
            structural_rows.append(structural)
        structural_digests.add(
            hashlib.sha256(
                json.dumps(
                    sorted(structural_rows, key=lambda row: row["run_id"]),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
            ).hexdigest(),
        )

    assert len(structural_digests) == 1
    assert all(
        len({summaries[index] for summaries in summaries_by_locale.values()}) == len(SUPPORTED_OUTPUT_LANGUAGES)
        for index in (0, 1)
    )
    assert all(
        summary and not summary.startswith("application.workflow.")
        for summaries in summaries_by_locale.values()
        for summary in summaries
    )


def test_workflow_action_projection_fails_closed_on_dead_or_insufficient_declarations() -> None:
    evidence = (
        ConditionEvidence(
            condition_id="workflow.draft.buildable",
            evidence_id="workflow.draft.build_failure",
            provenance=ConditionEvidenceProvenance.APPLICATION_STATE,
            values={"buildable": False},
        ),
    )
    with pytest.raises(KeyError, match="unknown operator action ID"):
        resolve_cli_precondition_action(
            PreconditionVerdict(
                failed_condition_id="workflow.draft.buildable",
                evidence=evidence,
                action=ActionReference(action_id="operator.missing.action"),
                conditionality=ActionConditionality.IMMEDIATE,
            ),
        )

    with pytest.raises(ValueError, match="arguments do not match catalogue declaration"):
        resolve_cli_precondition_action(
            PreconditionVerdict(
                failed_condition_id="workflow.draft.buildable",
                evidence=evidence,
                action=ActionReference(action_id="operator.modelo.work.calculate"),
                conditionality=ActionConditionality.IMMEDIATE,
            ),
        )


def test_workflow_action_projection_rejects_binding_provenance_outside_the_catalogue() -> None:
    verdict = PreconditionVerdict(
        failed_condition_id="workflow.draft.buildable",
        evidence=(
            ConditionEvidence(
                condition_id="workflow.draft.buildable",
                evidence_id="workflow.draft.build_failure",
                provenance=ConditionEvidenceProvenance.APPLICATION_STATE,
                values={"buildable": False},
            ),
        ),
        action=ActionReference(action_id="operator.modelo.work.calculate"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="work_unit_id",
                status=ActionArgumentStatus.RESOLVED,
                value="f" * 64,
                source=ActionArgumentSource.REQUEST_CONTEXT,
                source_key="work_unit_id",
            ),
        ),
        conditionality=ActionConditionality.IMMEDIATE,
    )
    with pytest.raises(ValueError, match="source contradicts catalogue"):
        resolve_cli_precondition_action(verdict)


def test_work_run_renderer_has_no_prose_or_legacy_action_authority() -> None:
    """AST guard the complete workflow-run payload and renderer boundary."""
    cli_root = Path(__file__).parents[1]
    source_scopes = {
        cli_root / "_modelo_work_runs_cli.py": {
            "_render_workflow_step_summary",
            "_workflow_run_payload",
            "_workflow_run_action_text",
            "_workflow_run_tab_line",
            "register_work_run_commands",
        },
        cli_root / "_modelo_aux_payloads.py": {
            "WorkflowRunPayload",
            "WorkRunsResult",
        },
    }
    violations: list[str] = []
    for path, names in source_scopes.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        scopes = tuple(
            node for node in tree.body if isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name in names
        )
        assert {scope.name for scope in scopes} == names
        for scope in scopes:
            for node in ast.walk(scope):
                if isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Name)
                        and node.func.id == "tr"
                        and any(keyword.arg == "default" for keyword in node.keywords)
                    ):
                        violations.append(f"{path.name}:{node.lineno}:tr(default=...)")
                    if (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get"
                        and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr == "details"
                    ):
                        violations.append(f"{path.name}:{node.lineno}:details.get")
                    if any(keyword.arg in {"next_action", "suggestion"} for keyword in node.keywords):
                        violations.append(f"{path.name}:{node.lineno}:legacy action keyword")
                elif isinstance(node, ast.Subscript):
                    if isinstance(node.value, ast.Attribute) and node.value.attr == "details":
                        violations.append(f"{path.name}:{node.lineno}:details subscript")
                elif isinstance(node, ast.Compare):
                    expression = ast.unparse(node)
                    if any(
                        marker in expression
                        for marker in (".summary", ".summary_locale_key", ".action", ".message", "next_action")
                    ) and any(
                        isinstance(item, ast.Constant) and isinstance(item.value, str) for item in ast.walk(node)
                    ):
                        violations.append(f"{path.name}:{node.lineno}:string recovery comparison")
                elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
                    prose_fallbacks = tuple(
                        item.value
                        for item in ast.walk(node)
                        if isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value != "-"
                    )
                    if prose_fallbacks:
                        violations.append(f"{path.name}:{node.lineno}:prose fallback")
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value == "next_action":
                        violations.append(f"{path.name}:{node.lineno}:next_action field")
                    if _RAW_COMMAND_PATTERN.search(node.value):
                        violations.append(f"{path.name}:{node.lineno}:raw CLI command")

    assert violations == []
