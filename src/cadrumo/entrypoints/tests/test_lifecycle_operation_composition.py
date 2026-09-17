"""Every exported lifecycle definition reaches the production composition root."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from ...application.modelo import operation_definitions as definitions_module
from ...application.operations.registry import OperationDefinition
from ...entrypoints.operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FACTORY_ARGUMENTS: dict[str, Any] = {
    "actor": "operator",
    "profile_resolver": lambda: None,
    "command_builder": lambda revision, path: None,
    # Port collaborators are consumed only when an executor is built, which this
    # suite never does; it proves composition, not execution.
    "calculation_action_ports_factory": lambda *args, **kwargs: None,
    "receipt_repository_factory": lambda *args, **kwargs: None,
    "export_ports_factory": lambda *args, **kwargs: None,
    "amendment_action_ports_factory": lambda *args, **kwargs: None,
    "work_lifecycle_ports_factory": lambda *args, **kwargs: None,
    "filing_action_ports_factory": lambda *args, **kwargs: None,
    "verification_repository_bundle_factory": lambda *args, **kwargs: None,
    "certificate_secret_backend_factory": lambda *args, **kwargs: None,
    "operator_scope_ports": object(),
}


def _definitions() -> dict[str, OperationDefinition]:
    definitions: dict[str, OperationDefinition] = {}
    for name in definitions_module.__all__:
        if not name.startswith("build_") or not name.endswith("_definition"):
            continue
        factory = getattr(definitions_module, name)
        parameters = inspect.signature(factory).parameters
        missing = [parameter for parameter in parameters if parameter not in _FACTORY_ARGUMENTS]
        if missing:
            pytest.fail(f"{name} needs arguments this conformance suite cannot supply: {missing}")
        definition = factory(**{name: _FACTORY_ARGUMENTS[name] for name in parameters})
        assert isinstance(definition, OperationDefinition)
        definitions[name] = definition
    return definitions


def test_every_exported_definition_reaches_the_production_registry() -> None:
    """No enrolment ships as capacity nothing can reach.

    These definitions sat exported and uncomposed: the registry knew none of
    them, so no frontend could submit one and no journal could record one. A
    definition that cannot be reached is indistinguishable from one that does
    not exist, except that it still has to be maintained.
    """
    exported = {definition.definition_id for definition in _definitions().values()}
    composed = {definition.definition_id for definition in build_production_operation_registry().definitions}

    assert exported, "no enrolment is exported; this assertion would be vacuous"
    assert exported <= composed, f"exported but never composed: {sorted(exported - composed)}"
