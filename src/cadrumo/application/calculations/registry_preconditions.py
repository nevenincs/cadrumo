"""Application policy for calculation-registry domain failure facts.

The registry domain names a failed condition and records only the facts it
observed.  This module is the sole calculation-layer owner of the typed action
or terminal outcome; it neither invents a command string nor redefines the
operator catalogue.
"""

from __future__ import annotations

from collections.abc import Mapping

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
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from ..operator_actions.preconditions import conditionality_for_binding, no_action_precondition_verdict

_PROFILE_EDIT_CONDITIONS = frozenset(
    {RegistryFailureCondition.TAXPAYER_MODEL_DECLARED, RegistryFailureCondition.MODELO_202_INCN_DECLARED}
)
_REGISTRY_RECORD_SAFETY_CONDITIONS = frozenset(
    {
        RegistryFailureCondition.QUERY_CASILLA_DECLARED,
        RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
        RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED,
    }
)
_SAFETY_CONDITIONS = _REGISTRY_RECORD_SAFETY_CONDITIONS | {RegistryFailureCondition.TREE_QUIESCENT}


def _domain_evidence(condition_id: str, facts: Mapping[str, str | int | bool]) -> tuple[ConditionEvidence, ...]:
    return (
        ConditionEvidence(
            condition_id=condition_id,
            evidence_id=f"{condition_id}.domain_evaluation",
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
            values=facts,
        ),
    )


def _profile_edit_verdict(condition_id: str, facts: Mapping[str, str | int | bool]) -> PreconditionVerdict:
    """Open the profile edit, bound to the profile the domain named when it named one."""
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
        evidence=_domain_evidence(condition_id, facts),
        action=ActionReference(action_id="operator.profile.edit"),
        argument_bindings=(binding,),
        missing_argument_names=("profile_name",) if binding.status is ActionArgumentStatus.MISSING else (),
        conditionality=conditionality_for_binding(binding),
    )


def _describe_modelo_verdict(condition_id: str, facts: Mapping[str, str | int | bool]) -> PreconditionVerdict:
    """Open the description of the modelo whose filing years scope the query."""
    binding = ActionArgumentBinding(
        argument_name="modelo",
        status=ActionArgumentStatus.RESOLVED,
        value=facts.get("modelo"),
        source=ActionArgumentSource.VERDICT_CONTEXT,
        source_key="modelo",
    )
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=_domain_evidence(condition_id, facts),
        action=ActionReference(action_id="operator.modelo.describe"),
        argument_bindings=(binding,),
        conditionality=ActionConditionality.IMMEDIATE,
    )


def _no_action_verdict(
    condition: RegistryFailureCondition, facts: Mapping[str, str | int | bool]
) -> PreconditionVerdict:
    """State why no catalogued action repairs a registry failure."""
    if condition is RegistryFailureCondition.DECLARATION_CONSISTENT:
        # The published registry is shipped data; no filer action repairs it.
        provenance, outcome = ActionEvidenceProvenance.REGISTRY_RECORD, NoRecoveryOutcome.TERMINAL
    elif condition is RegistryFailureCondition.ROWS_WITHIN_DECLARED_CAPACITY:
        # Which rows to keep is the filer's choice; no catalogued action states rows.
        provenance, outcome = ActionEvidenceProvenance.DOMAIN_EVALUATION, NoRecoveryOutcome.OPERATOR_DECISION
    elif condition in _SAFETY_CONDITIONS:
        provenance = (
            ActionEvidenceProvenance.REGISTRY_RECORD
            if condition in _REGISTRY_RECORD_SAFETY_CONDITIONS
            else ActionEvidenceProvenance.RUNTIME_OBSERVATION
        )
        outcome = NoRecoveryOutcome.SAFETY
    else:
        raise ValueError(f"unclassified calculation-registry failure condition: {condition}")
    return no_action_precondition_verdict(
        condition_id=condition.value, facts=facts, provenance=provenance, outcome=outcome
    )


def calculation_registry_failure_verdict(
    failure: RegistryFailureClassification,
) -> PreconditionVerdict:
    """Resolve one domain calculation-registry fact record into typed policy."""
    condition = failure.condition
    if not isinstance(condition, RegistryFailureCondition):
        raise ValueError(f"unclassified calculation-registry failure condition: {condition}")
    if condition in _PROFILE_EDIT_CONDITIONS:
        return _profile_edit_verdict(condition.value, failure.facts)
    if condition is RegistryFailureCondition.QUERY_FILING_YEAR_SCOPED:
        return _describe_modelo_verdict(condition.value, failure.facts)
    return _no_action_verdict(condition, failure.facts)


__all__ = ["calculation_registry_failure_verdict"]
