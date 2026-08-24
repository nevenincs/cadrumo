"""Canonical construction of terminal precondition verdicts."""

from __future__ import annotations

from collections.abc import Mapping

from ...core import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ._models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict


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


def active_profile_pointer_repair_verdict(
    *,
    condition_id: str,
    evidence_id: str,
    facts: Mapping[str, str | int | bool],
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
    "active_profile_pointer_repair_verdict",
    "corrupt_active_profile_pointer_verdict",
    "no_action_precondition_verdict",
]
