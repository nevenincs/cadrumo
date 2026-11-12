"""Application-owned recovery door for a refused profile access.

The runtime refuses a private operation with one stable reason. This module
decides what each reason means for the person: a session that is absent,
expired, locked or rebound is reopened by signing in, while a request whose
bound identity contradicts the admitted one, or an authority that is simply
not granted, has no recovery that would not widen access.
"""

from __future__ import annotations

from typing import Final

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.operator_action_enums import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ..operator_actions.models import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ..operator_actions.preconditions import no_action_precondition_verdict

SESSION_OPEN_CONDITION: Final = "profile.access.session_open"
ACCESS_ADMITTED_CONDITION: Final = "profile.access.admitted"
_EVIDENCE_ID: Final = "profile.access.denial"

# Reasons a fresh sign-in by the person repairs: the session is absent, spent,
# locked, or bound to a custody or runtime that has since changed.
_SIGN_IN_REASONS: Final[frozenset[AccessDenialCode]] = frozenset(
    {
        AccessDenialCode.AUTHENTICATION_REQUIRED,
        AccessDenialCode.SESSION_INACTIVE,
        AccessDenialCode.SESSION_EXPIRED,
        AccessDenialCode.PROFILE_LOCKED,
        AccessDenialCode.CUSTODY_CHANGED,
        AccessDenialCode.CUSTODY_RECOVERING,
        AccessDenialCode.RUNTIME_CHANGED,
        AccessDenialCode.FRESH_PASSWORD_REQUIRED,
    }
)


def access_refusal_verdict(reason: AccessDenialCode) -> PreconditionVerdict:
    """Return the sign-in door for a repairable session refusal, otherwise a terminal verdict.

    Every other reason, including a profile, connection or client mismatch,
    names an identity or authority the request may not have; no action is
    offered because none could widen access safely.
    """
    facts = {"access_denial": reason.value, "admitted": False}
    if reason in _SIGN_IN_REASONS:
        return PreconditionVerdict(
            failed_condition_id=SESSION_OPEN_CONDITION,
            evidence=(
                ConditionEvidence(
                    condition_id=SESSION_OPEN_CONDITION,
                    evidence_id=_EVIDENCE_ID,
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                    values=facts,
                ),
            ),
            action=ActionReference(action_id="operator.profile.login"),
            argument_bindings=(ActionArgumentBinding(argument_name="name", status=ActionArgumentStatus.MISSING),),
            missing_argument_names=("name",),
            conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
        )
    return no_action_precondition_verdict(
        condition_id=ACCESS_ADMITTED_CONDITION,
        evidence_id=_EVIDENCE_ID,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.TERMINAL,
    )


__all__ = ["ACCESS_ADMITTED_CONDITION", "SESSION_OPEN_CONDITION", "access_refusal_verdict"]
