"""The door of a refused reconciliation evidence file.

No catalogued action parses or supplies reconciliation evidence, so a file or
captured declaration the comparison cannot use is the operator's decision: a
different evidence file is named in a new request.
"""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict

RECONCILIATION_EVIDENCE_USABLE_CONDITION = "modelo.reconciliation.evidence.usable"
"""Condition identity the refused evidence fails."""


def reconciliation_evidence_decision_verdict() -> PreconditionVerdict:
    """The operator's decision on evidence the reconciliation cannot compare."""
    return no_action_precondition_verdict(
        condition_id=RECONCILIATION_EVIDENCE_USABLE_CONDITION,
        facts={"usable": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


__all__ = ["RECONCILIATION_EVIDENCE_USABLE_CONDITION", "reconciliation_evidence_decision_verdict"]
