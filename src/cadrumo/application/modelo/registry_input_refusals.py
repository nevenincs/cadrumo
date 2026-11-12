"""Declared doors of the refusals met where a Modelo input meets the selected registry.

Each cause is one failed condition with one declared door. An identifier the
operator supplied that the registry does not declare opens the listing of what
it does declare; a value the operator supplied that its casilla refuses opens
the value edit; a refusal no catalogued action repairs is the operator's
decision; a saved calculation read against another registry coordinate opens
the calculation; and a fault only the published authority, the stored data or
the calling code reaches is terminal, naming no command.

A broken registry declaration is not declared here: the calculation-registry
policy owns that condition, and :func:`registry_integrity_verdict` resolves it
through that owner so every reader serves the same verdict.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...domain.calculations.registry.errors import RegistryFailureClassification, RegistryFailureCondition
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.registry_preconditions import calculation_registry_failure_verdict
from ..operator_actions.catalogue import lookup_action
from ..operator_actions.models import ActionReference, ConditionEvidence, PreconditionVerdict
from .precondition_action_bindings import action_argument_bindings, recovery_conditionality

type FactValue = str | int | bool | Decimal

CASILLAS_ACTION_ID: Final[str] = "operator.modelo.casillas"
SET_VALUE_ACTION_ID: Final[str] = "operator.modelo.work.set_value"
BINDINGS_LIST_ACTION_ID: Final[str] = "operator.modelo.bindings.list"
CALCULATE_ACTION_ID: Final[str] = "operator.modelo.work.calculate"


class RegistryInputCondition(StrEnum):
    """One condition a Modelo input or saved projection fails against the selected registry."""

    CASILLA_DECLARED = "modelo.registry_input.casilla.declared"
    CASILLA_VALUE_ADMITTED = "modelo.registry_input.casilla_value.admitted"
    CASILLA_VALUE_SUPPORTED = "modelo.registry_input.casilla_value.supported"
    CASILLA_SCALAR = "modelo.registry_input.casilla.scalar"
    BINDING_DECLARED = "modelo.registry_input.binding.declared"
    MODELO_DECLARED = "modelo.registry_input.modelo.declared"
    INPUT_ADMITTED = "modelo.registry_input.input.admitted"
    AUTHORITY_AVAILABLE = "modelo.registry_input.authority.available"
    SAVED_CALCULATION_CURRENT = "modelo.registry_input.saved_calculation.current"
    SAVED_EVIDENCE_CONSISTENT = "modelo.registry_input.saved_evidence.consistent"
    REQUEST_CONSISTENT = "modelo.registry_input.request.consistent"


@dataclass(frozen=True, slots=True)
class RegistryInputRefusalSpec:
    """The declared door of one condition: an action, or the outcome when there is none."""

    action_id: str | None
    outcome: NoRecoveryOutcome | None
    provenance: ActionEvidenceProvenance


_DECISION = NoRecoveryOutcome.OPERATOR_DECISION
_TERMINAL = NoRecoveryOutcome.TERMINAL
_OPERATOR = ActionEvidenceProvenance.APPLICATION_STATE
_REGISTRY = ActionEvidenceProvenance.REGISTRY_RECORD
_CONDITION = RegistryInputCondition

REGISTRY_INPUT_REFUSAL_SPECS: Final[dict[RegistryInputCondition, RegistryInputRefusalSpec]] = {
    condition: RegistryInputRefusalSpec(action_id, outcome, provenance)
    for condition, action_id, outcome, provenance in (
        # The listing shows the identifiers the selected revision declares.
        (_CONDITION.CASILLA_DECLARED, CASILLAS_ACTION_ID, None, _REGISTRY),
        # The value edit states the casilla's value again.
        (_CONDITION.CASILLA_VALUE_ADMITTED, SET_VALUE_ACTION_ID, None, _REGISTRY),
        # A real value this version does not yet file is the operator's decision.
        (_CONDITION.CASILLA_VALUE_SUPPORTED, None, _DECISION, _REGISTRY),
        # A row field's values arrive on the detail rows the operator supplies.
        (_CONDITION.CASILLA_SCALAR, None, _DECISION, _REGISTRY),
        (_CONDITION.BINDING_DECLARED, BINDINGS_LIST_ACTION_ID, None, _REGISTRY),
        (_CONDITION.MODELO_DECLARED, BINDINGS_LIST_ACTION_ID, None, _REGISTRY),
        # An input on a surface no catalogued action addresses is restated there.
        (_CONDITION.INPUT_ADMITTED, None, _DECISION, _OPERATOR),
        # No catalogued action publishes the authority generation.
        (_CONDITION.AUTHORITY_AVAILABLE, None, _TERMINAL, ActionEvidenceProvenance.RUNTIME_OBSERVATION),
        # Calculating again records the work unit under the selected registry.
        (_CONDITION.SAVED_CALCULATION_CURRENT, CALCULATE_ACTION_ID, None, _OPERATOR),
        # Saved evidence that contradicts its own calculation is stored data no filer action repairs.
        (_CONDITION.SAVED_EVIDENCE_CONSISTENT, None, _TERMINAL, _OPERATOR),
        # The calling code contradicted itself; no filer action reaches it.
        (_CONDITION.REQUEST_CONSISTENT, None, _TERMINAL, _OPERATOR),
    )
}
"""Every condition's declared door, keyed by condition."""


def registry_input_verdict(
    condition: RegistryInputCondition,
    *,
    facts: Mapping[str, FactValue],
    action_arguments: Mapping[str, FactValue | None] | None = None,
) -> PreconditionVerdict:
    """Build the declared verdict of ``condition``.

    The declared action binds the arguments the refusal site knows and leaves
    every other argument the catalogue declares, and any it passes as ``None``,
    to the operator. The facts are
    the application's own observation: registry identifiers, never the
    operator's private values.
    """
    spec = REGISTRY_INPUT_REFUSAL_SPECS[condition]
    known: dict[str, FactValue] = {name: value for name, value in (action_arguments or {}).items() if value is not None}
    missing: tuple[str, ...] = ()
    if spec.action_id is not None:
        declared = tuple(item.argument_name for item in lookup_action(spec.action_id).argument_specifications)
        missing = tuple(dict.fromkeys(name for name in declared if name not in known))
    elif known:
        raise ValueError("a registry input refusal without an action binds no arguments")
    return PreconditionVerdict(
        failed_condition_id=condition.value,
        evidence=(
            ConditionEvidence(
                condition_id=condition.value,
                evidence_id=f"{condition.value}.observation",
                provenance=spec.provenance,
                values=facts,
            ),
        ),
        action=None if spec.action_id is None else ActionReference(action_id=spec.action_id),
        argument_bindings=action_argument_bindings(spec.action_id, known, missing),
        missing_argument_names=missing,
        conditionality=recovery_conditionality(spec.action_id, missing),
        no_recovery_outcome=spec.outcome,
    )


def listing_arguments(work_unit: WorkUnit | None) -> dict[str, FactValue]:
    """The registry listing's address of ``work_unit``, or nothing when the refusal site has no unit."""
    if work_unit is None:
        return {}
    return {
        "modelo": str(work_unit.modelo),
        "year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
    }


def casilla_value_arguments(casilla_ids: tuple[str, ...], work_unit: WorkUnit | None) -> dict[str, FactValue]:
    """The value edit's arguments a refusal knows: one refused casilla and its work unit."""
    arguments: dict[str, FactValue] = {}
    if len(casilla_ids) == 1:
        arguments["casilla_id"] = casilla_ids[0]
    if work_unit is not None:
        arguments["work_unit_id"] = work_unit.work_unit_id
    return arguments


def saved_calculation_verdict(work_unit_id: str, *, coordinate: str) -> PreconditionVerdict:
    """Open the calculation of a work unit whose saved calculation names another registry ``coordinate``."""
    return registry_input_verdict(
        RegistryInputCondition.SAVED_CALCULATION_CURRENT,
        facts={"work_unit_id": work_unit_id, "coordinate": coordinate, "current": False},
        action_arguments={"work_unit_id": work_unit_id},
    )


def saved_evidence_verdict(evidence: str) -> PreconditionVerdict:
    """The terminal verdict of saved ``evidence`` that contradicts the calculation it belongs to."""
    return registry_input_verdict(
        RegistryInputCondition.SAVED_EVIDENCE_CONSISTENT,
        facts={"evidence": evidence, "consistent": False},
    )


def request_verdict(request: str) -> PreconditionVerdict:
    """The terminal verdict of a ``request`` the calling code made inconsistent with itself."""
    return registry_input_verdict(
        RegistryInputCondition.REQUEST_CONSISTENT,
        facts={"request": request, "consistent": False},
    )


def registry_integrity_verdict(declaration: str) -> PreconditionVerdict:
    """Resolve a broken registry declaration through the calculation-registry policy."""
    return calculation_registry_failure_verdict(
        RegistryFailureClassification(
            condition=RegistryFailureCondition.DECLARATION_CONSISTENT,
            facts={"declaration": declaration, "consistent": False},
        )
    )


def filing_year_scope_verdict(modelo: str) -> PreconditionVerdict:
    """Resolve an unscoped point-in-time query through the calculation-registry policy."""
    return calculation_registry_failure_verdict(
        RegistryFailureClassification(
            condition=RegistryFailureCondition.QUERY_FILING_YEAR_SCOPED,
            facts={
                "modelo": modelo.strip(),
                "as_of_supplied": True,
                "filing_year_supplied": False,
                "query_scope": "unscoped_period",
            },
        )
    )


__all__ = [
    "BINDINGS_LIST_ACTION_ID",
    "CALCULATE_ACTION_ID",
    "CASILLAS_ACTION_ID",
    "REGISTRY_INPUT_REFUSAL_SPECS",
    "SET_VALUE_ACTION_ID",
    "RegistryInputCondition",
    "RegistryInputRefusalSpec",
    "casilla_value_arguments",
    "filing_year_scope_verdict",
    "listing_arguments",
    "registry_input_verdict",
    "registry_integrity_verdict",
    "request_verdict",
    "saved_calculation_verdict",
    "saved_evidence_verdict",
]
