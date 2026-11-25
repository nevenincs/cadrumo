"""Doors of the refusals that stop a filing draft from being approved.

A draft the filer approves with a blank approver, or before it is ready, is the
filer's decision to make again. A draft whose registry coordinate has moved
since it was built is rebuilt from the present registry, which no catalogued
action does, so that too is the filer's decision.
"""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict


def draft_approval_decision_verdict(reason: str) -> PreconditionVerdict:
    """The filer's decision on a draft approval that states too little or comes too early."""
    return no_action_precondition_verdict(
        condition_id=f"filing.draft.{reason}.admitted",
        facts={"reason": reason, "admitted": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def draft_registry_alignment_verdict(reason: str) -> PreconditionVerdict:
    """The filer's decision on a draft built under a registry coordinate that is no longer the law's."""
    return no_action_precondition_verdict(
        condition_id=f"filing.draft.{reason}.current",
        facts={"reason": reason, "current": False},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


__all__ = ["draft_approval_decision_verdict", "draft_registry_alignment_verdict"]
