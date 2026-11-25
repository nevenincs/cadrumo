"""Doors of the refusals that stop a profile fact from resolving into a calculation binding.

A profile fact the calculation needs and the profile does not hold is put right
by answering the profile's questions. A fact the profile holds but whose value
the binding refuses is the operator's decision, because no catalogued action
states the value again. A disagreement between a binding's declared contract
and the registry that consumes it is authored data no operator action repairs,
so it is terminal.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict, profile_required_facts_missing_verdict

_CONDITION_PREFIX: Final[str] = "modelo.profile_binding"

type _Fact = str | int | bool | Decimal


def _verdict(
    reason: str,
    facts: Mapping[str, _Fact],
    *,
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
) -> PreconditionVerdict:
    condition = f"{_CONDITION_PREFIX}.{reason}.resolvable"
    return no_action_precondition_verdict(
        condition_id=condition,
        facts={**facts, "resolvable": False},
        provenance=provenance,
        outcome=outcome,
    )


def profile_fact_value_refused_verdict(reason: str, facts: Mapping[str, _Fact]) -> PreconditionVerdict:
    """The operator's decision on a profile fact whose stored value the binding refuses."""
    return _verdict(
        reason,
        facts,
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def binding_contract_defect_verdict(reason: str, facts: Mapping[str, _Fact]) -> PreconditionVerdict:
    """The terminal verdict of a binding whose declared contract the registry contradicts."""
    return _verdict(
        reason,
        facts,
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        outcome=NoRecoveryOutcome.TERMINAL,
    )


_ASCENDANT_ROW_EDIT_ACTION_ID: Final[str] = "operator.profile.ascendiente.edit"


def ascendant_row_value_refused_verdict(index: int, leaf: str) -> PreconditionVerdict:
    """The edit of the ascendant row whose stored ``leaf`` the binding refuses.

    The row is known, so its edit door is addressed to it; the value to state
    again is the filer's, so the door asks for it.
    """
    condition = f"{_CONDITION_PREFIX}.ascendant_row_value.resolvable"
    index_binding = ActionArgumentBinding(
        argument_name="index",
        status=ActionArgumentStatus.RESOLVED,
        value=index,
        source=ActionArgumentSource.VERDICT_CONTEXT,
        source_key="index",
    )
    value_binding = ActionArgumentBinding(argument_name="ascendiente", status=ActionArgumentStatus.MISSING)
    return PreconditionVerdict(
        failed_condition_id=condition,
        evidence=(
            ConditionEvidence(
                condition_id=condition,
                evidence_id=f"{condition}.observation",
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                values={"index": index, "leaf": leaf, "resolvable": False},
            ),
        ),
        action=ActionReference(action_id=_ASCENDANT_ROW_EDIT_ACTION_ID),
        argument_bindings=(index_binding, value_binding),
        missing_argument_names=("ascendiente",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def profile_fact_absent_verdict(field_path: str) -> PreconditionVerdict:
    """The profile questions that state a fact the binding needs and the profile does not hold."""
    return profile_required_facts_missing_verdict(modelo=None, field_paths=(field_path,))


__all__ = [
    "ascendant_row_value_refused_verdict",
    "binding_contract_defect_verdict",
    "profile_fact_absent_verdict",
    "profile_fact_value_refused_verdict",
]
