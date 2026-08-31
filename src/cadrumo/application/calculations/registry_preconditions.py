"""Application policy for calculation-registry domain failure facts.

The registry domain names a failed condition and records only the facts it
observed.  This module is the sole calculation-layer owner of the typed action
or terminal outcome; it neither invents a command string nor redefines the
operator catalogue.
"""

from __future__ import annotations

from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ...domain.calculations.registry.errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
)
from ..operator_actions._models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from ..operator_actions._preconditions import conditionality_for_binding, no_action_precondition_verdict


def calculation_registry_failure_verdict(
    failure: RegistryFailureClassification,
) -> PreconditionVerdict:
    """Resolve one domain calculation-registry fact record into typed policy."""
    assert isinstance(failure.condition, RegistryFailureCondition), (
        f"unclassified calculation-registry failure condition: {failure.condition}"
    )
    condition_id = failure.condition.value
    facts = failure.facts
    if failure.condition in {
        RegistryFailureCondition.TAXPAYER_MODEL_DECLARED,
        RegistryFailureCondition.MODELO_202_INCN_DECLARED,
    }:
        profile_name = facts.get("profile_name")
        binding = (
            ActionArgumentBinding(
                argument_name="profile_name",
                status=ActionArgumentStatus.RESOLVED,
                value=profile_name,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="profile_name",
            )
            if isinstance(profile_name, str) and profile_name
            else ActionArgumentBinding(argument_name="profile_name", status=ActionArgumentStatus.MISSING)
        )
        return PreconditionVerdict(
            failed_condition_id=condition_id,
            evidence=(
                ConditionEvidence(
                    condition_id=condition_id,
                    evidence_id=f"{condition_id}.domain_evaluation",
                    provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                    values=facts,
                ),
            ),
            action=ActionReference(action_id="operator.profile.edit"),
            argument_bindings=(binding,),
            missing_argument_names=("profile_name",) if binding.status is ActionArgumentStatus.MISSING else (),
            conditionality=conditionality_for_binding(binding),
        )
    if failure.condition is RegistryFailureCondition.QUERY_FILING_YEAR_SCOPED:
        modelo = facts.get("modelo")
        binding = ActionArgumentBinding(
            argument_name="modelo",
            status=ActionArgumentStatus.RESOLVED,
            value=modelo,
            source=ActionArgumentSource.VERDICT_CONTEXT,
            source_key="modelo",
        )
        return PreconditionVerdict(
            failed_condition_id=condition_id,
            evidence=(
                ConditionEvidence(
                    condition_id=condition_id,
                    evidence_id=f"{condition_id}.domain_evaluation",
                    provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                    values=facts,
                ),
            ),
            action=ActionReference(action_id="operator.modelo.describe"),
            argument_bindings=(binding,),
            conditionality=ActionConditionality.IMMEDIATE,
        )
    assert failure.condition in {
        RegistryFailureCondition.QUERY_CASILLA_DECLARED,
        RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
        RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED,
        RegistryFailureCondition.TREE_QUIESCENT,
    }, f"unclassified calculation-registry failure condition: {failure.condition}"
    return no_action_precondition_verdict(
        condition_id=condition_id,
        facts=facts,
        provenance=(
            ActionEvidenceProvenance.REGISTRY_RECORD
            if failure.condition
            in {
                RegistryFailureCondition.QUERY_CASILLA_DECLARED,
                RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
                RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED,
            }
            else ActionEvidenceProvenance.RUNTIME_OBSERVATION
        ),
        outcome=NoRecoveryOutcome.SAFETY,
    )


__all__ = ["calculation_registry_failure_verdict"]
