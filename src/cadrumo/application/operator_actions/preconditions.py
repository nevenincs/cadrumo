"""Canonical construction of terminal precondition verdicts."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from .models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict


def conditionality_for_binding(binding: ActionArgumentBinding) -> ActionConditionality:
    """Return whether a recovery action needing this binding is immediately available.

    An action is materialisable right now (``IMMEDIATE``) unless the argument
    it depends on is still ``MISSING``, in which case the operator must
    supply it first (``REQUIRES_ARGUMENTS``).
    """
    return (
        ActionConditionality.REQUIRES_ARGUMENTS
        if binding.status is ActionArgumentStatus.MISSING
        else ActionConditionality.IMMEDIATE
    )


def no_action_precondition_verdict(
    *,
    condition_id: str,
    evidence_id: str | None = None,
    facts: Mapping[str, str | int | bool | Decimal],
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


def active_profile_pointer_repair_verdict(
    *,
    condition_id: str,
    evidence_id: str,
    facts: Mapping[str, str | int | bool | Decimal],
    provenance: ActionEvidenceProvenance,
) -> PreconditionVerdict:
    """Build the confirm-required repair outcome for one active-pointer failure."""
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=evidence_id,
                provenance=provenance,
                values=facts,
            ),
        ),
        action=ActionReference(action_id="operator.profile.repair_active_pointer"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="clear_active",
                status=ActionArgumentStatus.RESOLVED,
                value=True,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="clear_active",
            ),
            ActionArgumentBinding(argument_name="yes", status=ActionArgumentStatus.MISSING),
        ),
        missing_argument_names=("yes",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


PROFILE_SETUP_DECLARED_COMPLETE_CONDITION = "profile.setup.declared_complete"
"""Failed-condition identity: filing-grade work needs a profile declared set up."""

PROFILE_SETUP_STATE_EVIDENCE = "profile.setup.state"
"""Evidence identity for the persisted profile setup state observation."""


def profile_setup_incomplete_verdict(*, modelo: str, missing_required_field_count: int) -> PreconditionVerdict:
    """Build the completion outcome for modelo work refused by an unfinished profile setup.

    The condition belongs to the profile rather than to one modelo verb: every
    filing-grade leaf re-checks it, so the verdict names no leaf.  Setup is
    declared complete by one operator step that itself re-judges the record and
    names any outstanding field, which is why the same action serves a record
    with and without missing required facts.
    """
    if missing_required_field_count < 0:
        raise ValueError("missing_required_field_count cannot be negative")
    return PreconditionVerdict(
        failed_condition_id=PROFILE_SETUP_DECLARED_COMPLETE_CONDITION,
        evidence=(
            ConditionEvidence(
                condition_id=PROFILE_SETUP_DECLARED_COMPLETE_CONDITION,
                evidence_id=PROFILE_SETUP_STATE_EVIDENCE,
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                values={
                    "modelo": modelo,
                    "setup_declared_complete": False,
                    "missing_required_field_count": missing_required_field_count,
                },
            ),
        ),
        action=ActionReference(action_id="operator.profile.complete_setup"),
        conditionality=ActionConditionality.IMMEDIATE,
    )


def corrupt_active_profile_pointer_verdict(*, path: str) -> PreconditionVerdict:
    """Build the repair outcome for a core-observed corrupt active-profile pointer."""
    return active_profile_pointer_repair_verdict(
        condition_id="profile.active.pointer.valid",
        evidence_id="profile.active.pointer.corruption",
        facts={
            "path": path,
            "pointer_corrupt": True,
            "root_fallback_refused": True,
        },
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
    )


__all__ = [
    "PROFILE_SETUP_DECLARED_COMPLETE_CONDITION",
    "PROFILE_SETUP_STATE_EVIDENCE",
    "active_profile_pointer_repair_verdict",
    "conditionality_for_binding",
    "corrupt_active_profile_pointer_verdict",
    "no_action_precondition_verdict",
    "profile_setup_incomplete_verdict",
]
