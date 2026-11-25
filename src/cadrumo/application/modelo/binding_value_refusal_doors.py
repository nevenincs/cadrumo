"""Declared verdicts of a refused binding value, read from the error class itself."""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance
from ..operator_actions.models import PreconditionVerdict
from .preconditions import build_modelo_precondition_failure_for_scenario

_BINDING_LEAF = "modelo.bindings.resolve"


def binding_value_refused_verdict() -> PreconditionVerdict:
    """Return the verdict of a value its pinned contract refuses: the operator states another."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_BINDING_LEAF,
        scenario_id="modelo.bindings.value.refused",
        evidence_id="modelo.bindings.value",
        evidence_values={"admitted": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    ).verdict


def binding_value_contract_unsupported_verdict() -> PreconditionVerdict:
    """Return the verdict of a binding with no official value grammar: no value can be accepted."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_BINDING_LEAF,
        scenario_id="modelo.bindings.value_contract.unsupported",
        evidence_id="modelo.bindings.value_contract",
        evidence_values={"supported": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    ).verdict


__all__ = ["binding_value_contract_unsupported_verdict", "binding_value_refused_verdict"]
