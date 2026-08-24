"""Canonical construction of fact-only terminal precondition verdicts."""

from __future__ import annotations

from collections.abc import Mapping

from ...core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ._models import ConditionEvidence, PreconditionVerdict


def no_action_precondition_verdict(
    *,
    condition_id: str,
    evidence_id: str | None = None,
    facts: Mapping[str, str | int | bool],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
) -> PreconditionVerdict:
    """Build one fact-only terminal verdict without inventing a recovery action."""
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=evidence_id if evidence_id is not None else f"{condition_id}.observation",
                provenance=provenance,
                values=facts,
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=outcome,
    )


__all__ = ["no_action_precondition_verdict"]
