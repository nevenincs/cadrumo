"""Tests for the canonical no-action precondition-verdict builder."""

from __future__ import annotations

import ast
import inspect

import pytest

from ....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...workflow.profile_health import assess_active_profile_health
from .. import (
    active_profile_pointer_repair_verdict,
    corrupt_active_profile_pointer_verdict,
    no_action_precondition_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_no_action_precondition_verdict_preserves_caller_owned_terminal_facts() -> None:
    verdict = no_action_precondition_verdict(
        condition_id="test.operator_actions.remote_contract_valid",
        facts={"remote_contract_valid": False, "response_type": "str"},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    assert verdict.failed_condition_id == "test.operator_actions.remote_contract_valid"
    assert verdict.action is None
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].condition_id == "test.operator_actions.remote_contract_valid"
    assert verdict.evidence[0].evidence_id == "test.operator_actions.remote_contract_valid.observation"
    assert verdict.evidence[0].provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert verdict.evidence[0].values == {"remote_contract_valid": False, "response_type": "str"}


def test_no_action_precondition_verdict_preserves_caller_owned_evidence_id() -> None:
    verdict = no_action_precondition_verdict(
        condition_id="test.operator_actions.remote_contract_valid",
        evidence_id="test.operator_actions.remote_contract.observation",
        facts={"remote_contract_valid": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )

    assert verdict.evidence[0].evidence_id == "test.operator_actions.remote_contract.observation"


def test_active_profile_pointer_repair_verdict_preserves_the_catalogue_action_contract() -> None:
    verdict = active_profile_pointer_repair_verdict(
        condition_id="profile.active.pointer_registered",
        evidence_id="profile.active.pointer.health",
        facts={"registered_bucket": False, "repairable_by_clearing_pointer": True},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )

    assert verdict.failed_condition_id == "profile.active.pointer_registered"
    assert verdict.evidence[0].model_dump(mode="json") == {
        "condition_id": "profile.active.pointer_registered",
        "evidence_id": "profile.active.pointer.health",
        "provenance": "application_state",
        "values": {"registered_bucket": False, "repairable_by_clearing_pointer": True},
    }
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.repair_active_pointer"
    assert tuple(binding.model_dump(mode="json") for binding in verdict.argument_bindings) == (
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
    )
    assert verdict.missing_argument_names == ("yes",)
    assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS


def test_corrupt_active_profile_pointer_verdict_preserves_the_exact_core_observation() -> None:
    verdict = corrupt_active_profile_pointer_verdict(path="state/active-profile")

    assert verdict.failed_condition_id == "profile.active.pointer.valid"
    assert verdict.evidence[0].model_dump(mode="json") == {
        "condition_id": "profile.active.pointer.valid",
        "evidence_id": "profile.active.pointer.corruption",
        "provenance": "runtime_observation",
        "values": {
            "path": "state/active-profile",
            "pointer_corrupt": True,
            "root_fallback_refused": True,
        },
    }
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.repair_active_pointer"
    assert verdict.no_recovery_outcome is None


def test_workflow_delegates_pointer_repair_action_construction_to_operator_actions() -> None:
    profile_health_module = inspect.getmodule(assess_active_profile_health)
    assert profile_health_module is not None
    tree = ast.parse(inspect.getsource(profile_health_module))
    functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_pointer_repair_verdict" not in functions
    assert not any(
        isinstance(node, ast.Constant) and node.value == "operator.profile.repair_active_pointer"
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "active_profile_pointer_repair_verdict"
        for node in ast.walk(tree)
    )
