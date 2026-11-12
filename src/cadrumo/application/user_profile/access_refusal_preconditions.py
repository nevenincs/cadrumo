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


# Reasons the runtime refuses to protect an identity or authority boundary: the
# request names another profile, connection, client or parent, or asks for more
# than was granted. Offering any action here could widen access.
_SAFETY_REASONS: Final[frozenset[AccessDenialCode]] = frozenset(
    {
        AccessDenialCode.PROFILE_MISMATCH,
        AccessDenialCode.CONNECTION_MISMATCH,
        AccessDenialCode.CLIENT_MISMATCH,
        AccessDenialCode.PARENT_INVALID,
        AccessDenialCode.PRIVILEGE_EXPANSION,
        AccessDenialCode.CLOCK_INVALID,
        AccessDenialCode.FRONTEND_DENIED,
        AccessDenialCode.OPERATION_DENIED,
        AccessDenialCode.DISCLOSURE_DENIED,
        AccessDenialCode.PERIOD_DENIED,
        AccessDenialCode.ADMINISTRATION_DENIED,
    }
)

# Reasons the person resolves outside any catalogued action: waiting for the
# holder of a busy subject, unlocking the operating-system session, renewing a
# grant or key, approving automation, or acting in person.
_DECISION_REASONS: Final[frozenset[AccessDenialCode]] = frozenset(
    {
        AccessDenialCode.SUBJECT_BUSY,
        AccessDenialCode.OS_LOCKED,
        AccessDenialCode.OS_SESSION_UNAVAILABLE,
        AccessDenialCode.AUTOMATION_SUSPENDED,
        AccessDenialCode.GRANT_INACTIVE,
        AccessDenialCode.GRANT_EXPIRED,
        AccessDenialCode.KEY_INACTIVE,
        AccessDenialCode.KEY_EXPIRED,
        AccessDenialCode.PROVIDER_REQUIRED,
        AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED,
        AccessDenialCode.TRANSACTION_AUTHORITY_REQUIRED,
        AccessDenialCode.HUMAN_AUTHORITY_REQUIRED,
        AccessDenialCode.PERSON_ACT_REQUIRED,
    }
)


def _no_action_outcome(reason: AccessDenialCode) -> NoRecoveryOutcome:
    """Safety for a guarded boundary, the person's decision for what they resolve, else terminal."""
    if reason in _SAFETY_REASONS:
        return NoRecoveryOutcome.SAFETY
    if reason in _DECISION_REASONS:
        return NoRecoveryOutcome.OPERATOR_DECISION
    return NoRecoveryOutcome.TERMINAL


def access_refusal_verdict(reason: AccessDenialCode) -> PreconditionVerdict:
    """Return the sign-in door for a repairable session refusal, otherwise a no-action verdict.

    No other reason offers an action, because none could widen access safely;
    its outcome says whether the refusal guards a boundary, waits on the person,
    or reports an unavailable store or backend.
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
        outcome=_no_action_outcome(reason),
    )


__all__ = ["ACCESS_ADMITTED_CONDITION", "SESSION_OPEN_CONDITION", "access_refusal_verdict"]
