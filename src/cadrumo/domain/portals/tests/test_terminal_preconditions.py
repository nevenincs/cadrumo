"""Exact terminal-refusal contracts for the portal registry."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from types import ModuleType

import pytest

from ....core import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.errors import TerminalPreconditionErrorMixin
from .. import _errors as errors_module
from .. import _registry as registry_module
from .._registry import PORTAL_REGISTRY, _finalise_registry, get_portal, portals_for_modelo
from ..errors import (
    PortalIntegrityError,
    PortalRegistryError,
    PortalRegistryInvariant,
    PortalRegistryPrecondition,
    PortalValidationError,
    UnknownPortalError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@dataclass(frozen=True)
class _CarrierContract:
    invariant: PortalRegistryInvariant | None
    facts: tuple[tuple[str, str], ...]


def _contract(
    invariant: PortalRegistryInvariant | None,
    facts: tuple[tuple[str, str], ...],
) -> _CarrierContract:
    return _CarrierContract(invariant=invariant, facts=facts)


# The complete registry-side census: eight structural refusal sites and the
# one reachable malformed-modelo boundary.  Values are expressions, not just
# keys, so fact polarity and redaction shape cannot drift invisibly.
_REGISTRY_TERMINAL_CARRIERS: dict[str, _CarrierContract] = {
    "_check_replaced_by:portal_integrity_error:1": _contract(
        PortalRegistryInvariant.REPLACED_BY_TARGET_REGISTERED,
        (
            ("portal", "portal.value"),
            ("replaced_by", "target.value"),
            ("target_registered", "False"),
        ),
    ),
    "_finalise_registry:portal_integrity_error:1": _contract(
        PortalRegistryInvariant.PORTAL_ENTRY_UNIQUE,
        (("portal", "entry.portal.value"), ("entry_unique", "False")),
    ),
    "_finalise_registry:portal_integrity_error:2": _contract(
        PortalRegistryInvariant.PORTAL_ENUM_COVERAGE_COMPLETE,
        (("missing_count", "len(missing_values)"), ("enum_coverage_complete", "False")),
    ),
    "_finalise_registry:portal_integrity_error:3": _contract(
        PortalRegistryInvariant.PORTAL_ENUM_COVERAGE_COMPLETE,
        (("extra_count", "len(extra_values)"), ("enum_coverage_complete", "False")),
    ),
    "_finalise_registry:portal_integrity_error:4": _contract(
        PortalRegistryInvariant.ENTRY_PORTAL_MATCHES_MAPPING_KEY,
        (
            ("mapping_portal", "key.value"),
            ("entry_portal", "metadata.portal.value"),
            ("portal_matches_mapping_key", "False"),
        ),
    ),
    "_portal_consumer_binding:portal_integrity_error:1": _contract(
        PortalRegistryInvariant.PORTAL_ENUM_CONSUMER_RESOLVES,
        (
            ("modelo", "modelo_id"),
            ("revision_id", "str(revision_id)"),
            ("portal_enum_consumer_resolves", "False"),
        ),
    ),
    "_portal_consumer_binding:portal_integrity_error:2": _contract(
        PortalRegistryInvariant.PORTAL_ID_CONSUMER_RESOLVES,
        (
            ("modelo", "modelo_id"),
            ("revision_id", "str(revision_id)"),
            ("portal_id_consumer_resolves", "False"),
        ),
    ),
    "_registry_portal_bindings_for_modelo:portal_integrity_error:1": _contract(
        PortalRegistryInvariant.REGISTRY_PORTAL_BINDINGS_AVAILABLE,
        (
            ("modelo", "str(code)"),
            ("registry_portal_bindings_available", "False"),
            ("registry_error_type", "type(exc).__name__"),
        ),
    ),
    "portals_for_modelo:unknown_modelo_error:1": _contract(
        None,
        (("modelo", "str(code)"),),
    ),
}


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _keyword(call: ast.Call, name: str) -> ast.expr:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == name), None)
    assert value is not None, f"missing {name}"
    return value


def _assignments(node: ast.AST) -> dict[str, ast.expr]:
    assignments: dict[str, ast.expr] = {}
    for candidate in ast.walk(node):
        if isinstance(candidate, ast.Assign):
            for target in candidate.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = candidate.value
    return assignments


def _fact_expressions(
    call: ast.Call,
    assignments: dict[str, ast.expr] | None = None,
) -> tuple[tuple[str, str], ...]:
    facts = _keyword(call, "facts")
    if isinstance(facts, ast.Name) and assignments is not None:
        facts = assignments[facts.id]
    assert isinstance(facts, ast.Dict)
    values: list[tuple[str, str]] = []
    for key, value in zip(facts.keys, facts.values, strict=True):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        values.append((key.value, ast.unparse(value)))
    return tuple(values)


def _integrity_invariant(call: ast.Call) -> PortalRegistryInvariant:
    assert call.args
    value = call.args[0]
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "PortalRegistryInvariant"
    return PortalRegistryInvariant[value.attr]


def _registry_terminal_carriers() -> dict[str, ast.Call]:
    tree = ast.parse(inspect.getsource(registry_module))
    carriers: dict[str, ast.Call] = {}
    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
        occurrences: dict[str, int] = {}
        calls = sorted(
            (
                node
                for node in ast.walk(function)
                if isinstance(node, ast.Call)
                and _call_name(node.func) in {"portal_integrity_error", "unknown_modelo_error"}
            ),
            key=lambda node: node.lineno,
        )
        for call in calls:
            call_name = _call_name(call.func)
            assert call_name is not None
            occurrences[call_name] = occurrences.get(call_name, 0) + 1
            key = f"{function.name}:{call_name}:{occurrences[call_name]}"
            assert key not in carriers, f"duplicate portal terminal carrier {key}"
            carriers[key] = call
    return carriers


def _failure_constructor(function_name: str) -> tuple[ast.Call, dict[str, ast.expr]]:
    tree = ast.parse(inspect.getsource(errors_module))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function_name)
    return (
        next(
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and _call_name(node.func) == "PortalFailureClassification"
        ),
        _assignments(function),
    )


def _failure_condition(call: ast.Call) -> PortalRegistryPrecondition:
    value = _keyword(call, "condition")
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "PortalRegistryPrecondition"
    return PortalRegistryPrecondition[value.attr]


def _failure_policy(call: ast.Call) -> tuple[ActionEvidenceProvenance, NoRecoveryOutcome]:
    provenance = _keyword(call, "provenance")
    outcome = _keyword(call, "outcome")
    assert isinstance(provenance, ast.Attribute) and isinstance(provenance.value, ast.Name)
    assert isinstance(outcome, ast.Attribute) and isinstance(outcome.value, ast.Name)
    assert provenance.value.id == "ActionEvidenceProvenance"
    assert outcome.value.id == "NoRecoveryOutcome"
    return ActionEvidenceProvenance[provenance.attr], NoRecoveryOutcome[outcome.attr]


def _assert_exact_domain_failure(
    error: PortalRegistryError,
    *,
    condition: PortalRegistryPrecondition,
    facts: dict[str, str | int | bool],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
) -> None:
    assert isinstance(error, TerminalPreconditionErrorMixin)
    assert error.terminal_precondition_verdict is None
    failure = error.portal_failure
    assert failure is not None
    assert failure.condition is condition
    assert dict(failure.facts) == facts
    assert failure.provenance is provenance
    assert failure.outcome is outcome


def test_portal_terminal_carrier_totality_is_exact_and_mutation_sensitive() -> None:
    observed = _registry_terminal_carriers()

    assert set(observed) == set(_REGISTRY_TERMINAL_CARRIERS)
    for key, carrier in observed.items():
        expected = _REGISTRY_TERMINAL_CARRIERS[key]
        if _call_name(carrier.func) == "portal_integrity_error":
            assert _integrity_invariant(carrier) is expected.invariant
            assert _fact_expressions(carrier) == expected.facts
        else:
            assert _call_name(carrier.func) == "unknown_modelo_error"
            assert ast.unparse(carrier.args[0]) == expected.facts[0][1]


def test_portal_failure_classification_is_single_homed_in_domain() -> None:
    modules: tuple[ModuleType, ...] = (errors_module, registry_module)
    for module in modules:
        tree = ast.parse(inspect.getsource(module))
        imports_application = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and (
                (node.module is None and any(alias.name == "application" for alias in node.names))
                or (
                    node.module is not None
                    and (
                        node.module == "application" or node.module.startswith(("application.", "cadrumo.application"))
                    )
                )
            )
        ]
        constructors = {
            _call_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _call_name(node.func) in {"PreconditionVerdict", "ConditionEvidence"}
        }
        assert imports_application == [], module.__name__
        assert not constructors, module.__name__

    unknown_tree = ast.parse(inspect.getsource(UnknownPortalError))
    unknown_failure = next(
        node
        for node in ast.walk(unknown_tree)
        if isinstance(node, ast.Call) and _call_name(node.func) == "PortalFailureClassification"
    )
    assert _failure_condition(unknown_failure) is PortalRegistryPrecondition.PORTAL_REGISTERED
    assert _fact_expressions(unknown_failure, _assignments(unknown_tree)) == (
        ("portal", "portal"),
        ("portal_registered", "False"),
    )
    assert _failure_policy(unknown_failure) == (
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.OPERATOR_DECISION,
    )

    unknown_modelo_failure, unknown_modelo_assignments = _failure_constructor("unknown_modelo_error")
    assert _failure_condition(unknown_modelo_failure) is PortalRegistryPrecondition.MODELO_CODE_RECOGNISED
    assert _fact_expressions(unknown_modelo_failure, unknown_modelo_assignments) == (
        ("modelo", "modelo"),
        ("modelo_code_recognised", "False"),
    )
    assert _failure_policy(unknown_modelo_failure) == (
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        NoRecoveryOutcome.OPERATOR_DECISION,
    )

    integrity_failure, _integrity_assignments = _failure_constructor("portal_integrity_error")
    assert _failure_condition(integrity_failure) is PortalRegistryPrecondition.INTEGRITY_VALID
    assert ast.unparse(_keyword(integrity_failure, "facts")) == "context"
    assert _failure_policy(integrity_failure) == (
        ActionEvidenceProvenance.APPLICATION_STATE,
        NoRecoveryOutcome.SAFETY,
    )


def test_get_portal_unknown_identifier_has_exact_domain_classification() -> None:
    with pytest.raises(UnknownPortalError) as raised:
        get_portal("not_a_portal")

    _assert_exact_domain_failure(
        raised.value,
        condition=PortalRegistryPrecondition.PORTAL_REGISTERED,
        facts={"portal": "not_a_portal", "portal_registered": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_get_portal_has_exactly_the_two_registered_refusal_carriers() -> None:
    tree = ast.parse(inspect.getsource(registry_module))
    get_portal_function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "get_portal"
    )
    assert [
        ast.unparse(call.args[0])
        for call in sorted(
            (
                node
                for node in ast.walk(get_portal_function)
                if isinstance(node, ast.Call) and _call_name(node.func) == "UnknownPortalError"
            ),
            key=lambda node: node.lineno,
        )
    ] == ["portal", "member.value"]


def test_portals_for_malformed_modelo_has_exact_domain_classification() -> None:
    with pytest.raises(PortalValidationError) as raised:
        portals_for_modelo("not-a-modelo")

    _assert_exact_domain_failure(
        raised.value,
        condition=PortalRegistryPrecondition.MODELO_CODE_RECOGNISED,
        facts={"modelo": "not-a-modelo", "modelo_code_recognised": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_duplicate_portal_registry_entry_has_exact_integrity_classification() -> None:
    duplicate = next(iter(PORTAL_REGISTRY.values()))
    with pytest.raises(PortalIntegrityError) as raised:
        _finalise_registry((duplicate, duplicate))

    _assert_exact_domain_failure(
        raised.value,
        condition=PortalRegistryPrecondition.INTEGRITY_VALID,
        facts={
            "invariant": PortalRegistryInvariant.PORTAL_ENTRY_UNIQUE.value,
            "portal": duplicate.portal.value,
            "entry_unique": False,
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.SAFETY,
    )
