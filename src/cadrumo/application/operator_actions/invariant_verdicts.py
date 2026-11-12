"""The terminal outcome of a broken internal invariant.

An internal invariant names a condition the program or its stored state must
hold. When one fails, no command the operator can run repairs it, so the
refusal names the invariant and states that no recovery exists.
"""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .models import PreconditionVerdict
from .preconditions import no_action_precondition_verdict

INTERNAL_INVARIANT_CONDITION = "internal.invariant.holds"
"""Condition identity every internal-invariant verdict fails."""


def internal_invariant_verdict(invariant: str) -> PreconditionVerdict:
    """Return the terminal verdict of one broken invariant, named by a stable locale-neutral token."""
    return no_action_precondition_verdict(
        condition_id=INTERNAL_INVARIANT_CONDITION,
        evidence_id=f"{INTERNAL_INVARIANT_CONDITION}.{invariant}",
        facts={"invariant": invariant, "holds": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.TERMINAL,
    )


__all__ = ["INTERNAL_INVARIANT_CONDITION", "internal_invariant_verdict"]
