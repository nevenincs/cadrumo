"""Tests for the deferred LLM terminal-verdict adapter."""

from __future__ import annotations

import pytest

from ...core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .._preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_llm_no_recovery_verdict_preserves_terminal_observation_contract() -> None:
    verdict = llm_no_recovery_verdict(
        LLMPreconditionCondition.REQUEST_PROMPT_NONEMPTY,
        facts={"prompt_present": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )

    assert verdict.failed_condition_id == "llm.request.prompt_nonempty"
    assert verdict.action is None
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY
    assert verdict.evidence[0].model_dump(mode="json") == {
        "condition_id": "llm.request.prompt_nonempty",
        "evidence_id": "llm.request.prompt_nonempty.observation",
        "provenance": "runtime_observation",
        "values": {"prompt_present": False},
    }
