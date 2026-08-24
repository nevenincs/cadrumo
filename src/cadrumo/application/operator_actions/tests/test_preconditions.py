"""Tests for the canonical no-action precondition-verdict builder."""

from __future__ import annotations

import pytest

from ....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .. import no_action_precondition_verdict

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
