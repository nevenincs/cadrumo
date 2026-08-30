"""Tests for observed condition/action assertions derived from the production matrix."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.application.modelo._preconditions import build_modelo_precondition_failure
from cadrumo.application.operator_actions import no_action_precondition_verdict
from cadrumo.core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from cadrumo.core.json_contract import EnvelopeStatus

from .._action_coverage import LeafConditionScenario, production_leaf_condition_scenario_matrix
from .._models import (
    ExitCodeScenario,
    ExitCodeVerdict,
    ObservedProductionActionAssertion,
    observe_production_action,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _actionable_coverage() -> LeafConditionScenario:
    """Return a live action profile whose canonical declaration needs no values."""
    return next(
        coverage
        for coverage in production_leaf_condition_scenario_matrix().rows
        if coverage.profile.resolved_action is not None
        and not coverage.profile.resolved_action.declaration.argument_specifications
    )


def _terminal_coverage() -> LeafConditionScenario:
    """Return one current explicit no-recovery profile from production."""
    return next(
        coverage
        for coverage in production_leaf_condition_scenario_matrix().rows
        if coverage.profile.declaration.no_recovery_outcome is not None
    )


def test_observed_action_assertion_uses_a_live_profile_not_a_scenario_authored_action() -> None:
    """A real production verdict agrees only through the resolved matrix profile."""
    coverage = _actionable_coverage()
    declared_action = coverage.profile.declaration.action
    assert declared_action is not None

    failure = build_modelo_precondition_failure(
        subject_leaf_key=coverage.subject_leaf_key,
        condition_id=coverage.condition_id,
        scenario_id=coverage.scenario_id,
        evidence_id="agent_eval.production_action.observation",
        evidence_values={"observed": True},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_id=declared_action.action_id,
    )

    assertion = observe_production_action(coverage, failure.verdict)

    assert assertion.passed
    assert assertion.observed_condition_id == coverage.condition_id
    assert assertion.observed_action_id == declared_action.action_id
    assert assertion.observed_no_recovery_outcome is None


def test_observed_terminal_assertion_compares_the_explicit_production_outcome() -> None:
    """A no-action verdict remains accountable to its declared terminal outcome."""
    coverage = _terminal_coverage()

    failure = build_modelo_precondition_failure(
        subject_leaf_key=coverage.subject_leaf_key,
        condition_id=coverage.condition_id,
        scenario_id=coverage.scenario_id,
        evidence_id="agent_eval.production_terminal.observation",
        evidence_values={"observed": True},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )

    assertion = observe_production_action(coverage, failure.verdict)

    assert assertion.passed
    assert assertion.observed_action_id is None
    assert assertion.observed_no_recovery_outcome is coverage.profile.declaration.no_recovery_outcome


def test_observed_action_assertion_rejects_a_real_but_wrong_closed_outcome() -> None:
    """An observed terminal verdict cannot impersonate an actionable production profile."""
    coverage = _actionable_coverage()
    observed = no_action_precondition_verdict(
        condition_id=coverage.condition_id,
        facts={"observed": True},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.TERMINAL,
    )

    assertion = observe_production_action(coverage, observed)

    assert assertion.condition_matches
    assert not assertion.action_matches
    assert not assertion.no_recovery_outcome_matches
    assert not assertion.passed


def test_exit_scenario_and_verdict_carry_production_assertions_not_expected_action_fields() -> None:
    """The eval boundary rejects legacy scenario-command expectations and requires observation evidence."""
    coverage = _actionable_coverage()
    scenario = ExitCodeScenario(
        name="production-profile-exit-verdict",
        command=coverage.subject_leaf_key,
        expected_exit_code=1,
        tool_result_status=EnvelopeStatus.WARNING,
        leaf_condition_scenario=coverage.identity,
    )

    assert tuple(ExitCodeScenario.model_fields) == (
        "name",
        "command",
        "expected_exit_code",
        "tool_result_status",
        "leaf_condition_scenario",
    )
    assert tuple(ExitCodeVerdict.model_fields) == (
        "scenario",
        "exit_code_matches",
        "envelope_well_formed",
        "status_is_non_success",
        "production_action_assertion",
        "failures",
    )
    assert scenario.leaf_condition_scenario == coverage.identity
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ExitCodeScenario.model_validate(
            {
                **scenario.model_dump(),
                "expected_next_action": "modelo.work.fabricated",
            },
        )

    assertion = ObservedProductionActionAssertion(
        leaf_condition_scenario=coverage.identity,
        observed_condition_id=coverage.condition_id,
        observed_action_id=coverage.profile.declaration.action.action_id
        if coverage.profile.declaration.action is not None
        else None,
        observed_no_recovery_outcome=None,
        condition_matches=True,
        action_matches=True,
        no_recovery_outcome_matches=True,
    )
    verdict = ExitCodeVerdict(
        scenario=scenario.name,
        exit_code_matches=True,
        envelope_well_formed=True,
        status_is_non_success=True,
        production_action_assertion=assertion,
    )
    assert verdict.passed

    with pytest.raises(ValidationError, match="exactly one action or no-recovery"):
        ObservedProductionActionAssertion(
            leaf_condition_scenario=coverage.identity,
            observed_condition_id=coverage.condition_id,
            observed_action_id=None,
            observed_no_recovery_outcome=None,
            condition_matches=True,
            action_matches=False,
            no_recovery_outcome_matches=False,
        )
