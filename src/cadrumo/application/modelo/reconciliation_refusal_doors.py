"""The doors of the refused reconciliation sources.

No catalogued action parses or supplies reconciliation evidence, so a file or
captured declaration the comparison cannot use is the operator's decision: a
different evidence file is named in a new request. A declaration source that
no modelo enrolls is the same decision: a downloaded justificante is reconciled
instead. A difference the registry revision cannot ground in a declared box is
a fault of the revision or the program, which no operator action repairs.
"""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict

RECONCILIATION_EVIDENCE_USABLE_CONDITION = "modelo.reconciliation.evidence.usable"
"""Condition identity the refused evidence fails."""

RECONCILIATION_DECLARATION_SOURCE_CONDITION = "modelo.reconciliation.declaration_source.enrolled"
"""Condition identity the unenrolled declaration source fails."""

RECONCILIATION_DIFFERENCE_GROUNDED_CONDITION = "modelo.reconciliation.difference.grounded"
"""Condition identity a difference in an undeclared box fails."""


def reconciliation_evidence_decision_verdict() -> PreconditionVerdict:
    """The operator's decision on evidence the reconciliation cannot compare."""
    return no_action_precondition_verdict(
        condition_id=RECONCILIATION_EVIDENCE_USABLE_CONDITION,
        facts={"usable": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def reconciliation_declaration_source_decision_verdict(modelo: str | None = None) -> PreconditionVerdict:
    """The operator's decision to reconcile a justificante, because no modelo here enrolls the declaration source."""
    return no_action_precondition_verdict(
        condition_id=RECONCILIATION_DECLARATION_SOURCE_CONDITION,
        facts={"enrolled": False} if modelo is None else {"enrolled": False, "modelo": modelo},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def reconciliation_undeclared_difference_verdict(casilla_id: str) -> PreconditionVerdict:
    """The terminal verdict of a difference whose box the registry revision does not declare."""
    return no_action_precondition_verdict(
        condition_id=RECONCILIATION_DIFFERENCE_GROUNDED_CONDITION,
        facts={"casilla_id": casilla_id, "declared": False},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        outcome=NoRecoveryOutcome.TERMINAL,
    )


__all__ = [
    "RECONCILIATION_DECLARATION_SOURCE_CONDITION",
    "RECONCILIATION_DIFFERENCE_GROUNDED_CONDITION",
    "RECONCILIATION_EVIDENCE_USABLE_CONDITION",
    "reconciliation_declaration_source_decision_verdict",
    "reconciliation_evidence_decision_verdict",
    "reconciliation_undeclared_difference_verdict",
]
