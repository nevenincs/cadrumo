"""The verdict a refusing agent service hands a reader, for tests that only carry it."""

from __future__ import annotations

from ...core.model_roles import ModelRole
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict

__all__ = ["model_not_installed_verdict"]


def model_not_installed_verdict(role: ModelRole) -> PreconditionVerdict:
    """Return the verdict for the agent refusing ``role`` because the selected model is not installed."""
    return no_action_precondition_verdict(
        condition_id="llm.agent.model_run_completed",
        facts={
            "model_run_refusal": "model_not_installed",
            "model_role": role.value,
            "role": role.value,
            "role_model_installed": False,
        },
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
