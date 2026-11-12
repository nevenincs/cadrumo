"""Verdict builders for the lifecycle refusals whose door is one catalogued action or one stated outcome.

A refusal of an operator-correctable input or a stale view opens the catalogued
action that states the input or reads the view again, with the arguments the
refusal site knows bound. A refusal that no catalogued action repairs is the
operator's decision when a different choice would be admitted, a safety stop
when a guarded boundary refused, and terminal when only stored data, the
registry or the calling code can have caused it. Every builder states
application observations, never the operator's private values.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions.catalogue import lookup_action
from ..operator_actions.models import ActionReference, ConditionEvidence, PreconditionVerdict
from .precondition_action_bindings import action_argument_bindings, recovery_conditionality

type FactValue = str | int | bool | Decimal

WORK_LIST_ACTION_ID: Final[str] = "operator.modelo.work.list"
WORK_STATUS_ACTION_ID: Final[str] = "operator.modelo.work.status"
WORK_REVISIONS_ACTION_ID: Final[str] = "operator.modelo.work.revisions"
WORK_CALCULATE_ACTION_ID: Final[str] = "operator.modelo.work.calculate"
WORK_SET_VALUE_ACTION_ID: Final[str] = "operator.modelo.work.set_value"
WORK_VERIFY_ACTION_ID: Final[str] = "operator.modelo.work.verify"
WORK_CREATE_ACTION_ID: Final[str] = "operator.modelo.work.create"
DESCRIBE_ACTION_ID: Final[str] = "operator.modelo.describe"
CASILLAS_ACTION_ID: Final[str] = "operator.modelo.casillas"
BINDINGS_ACTION_ID: Final[str] = "operator.modelo.bindings.list"
FILING_RECORD_LIST_ACTION_ID: Final[str] = "operator.modelo.filing_record.list"
FILED_PULL_ACTION_ID: Final[str] = "operator.live.filed.pull"
PROFILE_EDIT_ACTION_ID: Final[str] = "operator.profile.edit"
PROFILE_LIST_ACTION_ID: Final[str] = "operator.profile.list"
FILING_RECORD_IMPORT_ACTION_ID: Final[str] = "operator.modelo.filing_record.import"
VERIFICATION_REPORT_LIST_ACTION_ID: Final[str] = "operator.modelo.verification_report.list"


def action_door_verdict(
    condition: str,
    action_id: str,
    *,
    facts: Mapping[str, FactValue],
    arguments: Mapping[str, FactValue | None] | None = None,
    provenance: ActionEvidenceProvenance = ActionEvidenceProvenance.APPLICATION_STATE,
) -> PreconditionVerdict:
    """Open ``action_id`` for the failed ``condition``, binding the arguments the refusal site knows.

    Any argument the catalogue declares that the site did not bind, or bound to
    ``None``, is left to the operator.
    """
    known: dict[str, FactValue] = {name: value for name, value in (arguments or {}).items() if value is not None}
    declared = tuple(item.argument_name for item in lookup_action(action_id).argument_specifications)
    missing = tuple(dict.fromkeys(name for name in declared if name not in known))
    return PreconditionVerdict(
        failed_condition_id=condition,
        evidence=(
            ConditionEvidence(
                condition_id=condition,
                evidence_id=f"{condition}.observation",
                provenance=provenance,
                values=facts,
            ),
        ),
        action=ActionReference(action_id=action_id),
        argument_bindings=action_argument_bindings(action_id, known, missing),
        missing_argument_names=missing,
        conditionality=recovery_conditionality(action_id, missing),
    )


def outcome_door_verdict(
    condition: str,
    outcome: NoRecoveryOutcome,
    *,
    facts: Mapping[str, FactValue],
    provenance: ActionEvidenceProvenance = ActionEvidenceProvenance.APPLICATION_STATE,
) -> PreconditionVerdict:
    """State that the failed ``condition`` has no catalogued action, and why."""
    return PreconditionVerdict(
        failed_condition_id=condition,
        evidence=(
            ConditionEvidence(
                condition_id=condition,
                evidence_id=f"{condition}.observation",
                provenance=provenance,
                values=facts,
            ),
        ),
        conditionality=recovery_conditionality(None, ()),
        no_recovery_outcome=outcome,
    )


def decision_door_verdict(
    condition: str,
    *,
    facts: Mapping[str, FactValue],
    provenance: ActionEvidenceProvenance = ActionEvidenceProvenance.APPLICATION_STATE,
) -> PreconditionVerdict:
    """The operator's decision: a different choice would be admitted, and no action makes it."""
    return outcome_door_verdict(condition, NoRecoveryOutcome.OPERATOR_DECISION, facts=facts, provenance=provenance)


def safety_door_verdict(
    condition: str,
    *,
    facts: Mapping[str, FactValue],
    provenance: ActionEvidenceProvenance = ActionEvidenceProvenance.APPLICATION_STATE,
) -> PreconditionVerdict:
    """A guarded boundary refused; no action may pass it."""
    return outcome_door_verdict(condition, NoRecoveryOutcome.SAFETY, facts=facts, provenance=provenance)


def terminal_door_verdict(
    condition: str,
    *,
    facts: Mapping[str, FactValue],
    provenance: ActionEvidenceProvenance = ActionEvidenceProvenance.APPLICATION_STATE,
) -> PreconditionVerdict:
    """Stored data, the registry or the calling code broke the condition; no operator action repairs it."""
    return outcome_door_verdict(condition, NoRecoveryOutcome.TERMINAL, facts=facts, provenance=provenance)


def _reason_facts(reason: str) -> dict[str, FactValue]:
    return {"reason": reason, "holds": False}


def registry_defect_verdict(reason: str) -> PreconditionVerdict:
    """The terminal verdict of a published registry that contradicts what the application reads from it."""
    return terminal_door_verdict(
        f"modelo.refusal.{reason}.holds",
        facts=_reason_facts(reason),
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
    )


def stored_defect_verdict(reason: str) -> PreconditionVerdict:
    """The terminal verdict of stored data that contradicts what the application wrote."""
    return terminal_door_verdict(
        f"modelo.refusal.{reason}.holds",
        facts=_reason_facts(reason),
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


def caller_defect_verdict(reason: str) -> PreconditionVerdict:
    """The terminal verdict of calling code that broke a contract the operator cannot reach."""
    return terminal_door_verdict(f"modelo.refusal.{reason}.holds", facts=_reason_facts(reason))


def operator_choice_verdict(reason: str) -> PreconditionVerdict:
    """The operator's decision on a choice or value the call stated and the rules refuse."""
    return decision_door_verdict(f"modelo.refusal.{reason}.holds", facts=_reason_facts(reason))


def safety_stop_verdict(reason: str) -> PreconditionVerdict:
    """A guarded boundary stopped the request; the reason names the boundary."""
    return safety_door_verdict(f"modelo.refusal.{reason}.holds", facts=_reason_facts(reason))


__all__ = [
    "BINDINGS_ACTION_ID",
    "CASILLAS_ACTION_ID",
    "DESCRIBE_ACTION_ID",
    "FILED_PULL_ACTION_ID",
    "FILING_RECORD_IMPORT_ACTION_ID",
    "FILING_RECORD_LIST_ACTION_ID",
    "PROFILE_EDIT_ACTION_ID",
    "PROFILE_LIST_ACTION_ID",
    "VERIFICATION_REPORT_LIST_ACTION_ID",
    "WORK_CALCULATE_ACTION_ID",
    "WORK_CREATE_ACTION_ID",
    "WORK_LIST_ACTION_ID",
    "WORK_REVISIONS_ACTION_ID",
    "WORK_SET_VALUE_ACTION_ID",
    "WORK_STATUS_ACTION_ID",
    "WORK_VERIFY_ACTION_ID",
    "FactValue",
    "action_door_verdict",
    "caller_defect_verdict",
    "decision_door_verdict",
    "operator_choice_verdict",
    "outcome_door_verdict",
    "registry_defect_verdict",
    "safety_door_verdict",
    "safety_stop_verdict",
    "stored_defect_verdict",
    "terminal_door_verdict",
]
