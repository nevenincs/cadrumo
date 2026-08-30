"""Conformance over every enrolled modelo lifecycle operation.

The denominator here is DERIVED from the definitions module, never listed. A
hand-maintained list of enrolments to check cannot report the enrolment nobody
added to it, so a seventh operation landing tomorrow is covered by every
assertion below without anyone remembering to extend this file.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Any

import pytest

from ....core import OperationDurability, OperationEffect
from ...operations.capabilities import OperationRequestStoragePolicy
from ...operations.models import CredentialFreeOperationRequest
from ...operations.registry import OperationDefinition
from .. import operation_definitions as definitions_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Arguments every enrolment factory may ask for. A factory that needs
#: something absent here fails loudly rather than being skipped.
_FACTORY_ARGUMENTS: dict[str, Any] = {
    "actor": "operator",
    "profile_resolver": lambda: None,
    "command_builder": lambda revision, path: None,
}

_KNOWN_AUTHORITIES = {
    "rename_work_unit",
    "discard_work_unit",
    "verify_modelo_revision",
    "file_modelo_revision",
    "export_modelo_revision",
    "amend_modelo_revision",
    "apply_modelo_edit",
}


def _definition_factories() -> dict[str, Any]:
    """Return every enrolment factory this module exports."""
    factories = {
        name: getattr(definitions_module, name)
        for name in definitions_module.__all__
        if name.startswith("build_") and name.endswith("_definition")
    }
    if not factories:
        pytest.fail("no enrolment factory is exported; the conformance denominator would be empty")
    return factories


def _build(factory: Any) -> OperationDefinition:
    """Invoke one factory with only the arguments it declares."""
    parameters = inspect.signature(factory).parameters
    missing = [name for name in parameters if name not in _FACTORY_ARGUMENTS]
    if missing:
        pytest.fail(f"{factory.__name__} needs arguments this conformance suite cannot supply: {missing}")
    built = factory(**{name: _FACTORY_ARGUMENTS[name] for name in parameters})
    assert isinstance(built, OperationDefinition)
    return built


def _definitions() -> dict[str, OperationDefinition]:
    return {name: _build(factory) for name, factory in _definition_factories().items()}


def test_the_denominator_covers_every_declared_definition_id() -> None:
    """Every declared operation id has an enrolment, and every enrolment an id."""
    declared = {
        getattr(definitions_module, name)
        for name in definitions_module.__all__
        if name.endswith("_OPERATION_DEFINITION_ID")
    }
    enrolled = {definition.definition_id for definition in _definitions().values()}

    assert declared, "no operation id is declared"
    assert declared == enrolled, f"declared and enrolled ids diverge: {declared ^ enrolled}"


def test_no_two_enrolments_redeclare_one_subject() -> None:
    """An id or a schema id claimed twice would make one enrolment unreachable."""
    definitions = list(_definitions().values())
    ids = [definition.definition_id for definition in definitions]

    assert len(set(ids)) == len(ids), f"duplicate definition ids: {ids}"

    registrations = [
        getattr(definitions_module, name)(definition)
        for name, definition in (
            (factory_name.replace("_definition", "_registration"), definition)
            for factory_name, definition in _definitions().items()
        )
        if hasattr(definitions_module, name)
    ]
    schema_ids = [binding.identity.schema_id for reg in registrations for binding in reg.schema_bindings]

    assert len(set(schema_ids)) == len(schema_ids), f"duplicate schema ids: {schema_ids}"


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_each_enrolment_is_recorded_and_journals_a_credential_free_request(factory_name: str) -> None:
    """Lifecycle work is durable, and its request is safe to journal."""
    definition = _build(_definition_factories()[factory_name])

    assert definition.capabilities.durability is OperationDurability.RECORDED
    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    assert issubclass(definition.request_type, CredentialFreeOperationRequest)


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_each_enrolment_admits_an_uncertain_outcome(factory_name: str) -> None:
    """An interrupted lifecycle write must be reportable as unknown."""
    definition = _build(_definition_factories()[factory_name])

    assert OperationEffect.UNKNOWN in definition.capabilities.permitted_effects


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_each_executor_delegates_to_exactly_one_known_writer(factory_name: str) -> None:
    """Every enrolment supervises one authority and invents no second path."""
    definition = _build(_definition_factories()[factory_name])
    source = inspect.getsource(definition.executor_factory.executor_type)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    writers = called & _KNOWN_AUTHORITIES

    assert len(writers) == 1, f"{factory_name} delegates to {writers or 'no known writer'}"


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_no_executor_opens_its_own_repository(factory_name: str) -> None:
    """The writer owns the atomic set; an enrolment that reached past it would tear it."""
    definition = _build(_definition_factories()[factory_name])
    source = inspect.getsource(definition.executor_factory.executor_type)

    for forbidden in ("Repository(", "upsert_", "BucketEventHistory"):
        assert forbidden not in source, f"{factory_name} opens a write path around its writer: {forbidden}"


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_no_result_receipt_carries_operand_material(factory_name: str) -> None:
    """A result names and fingerprints; it never ships the material itself."""
    definition = _build(_definition_factories()[factory_name])
    result_type = definition.result_type

    assert result_type is not None, f"{factory_name} declares no result receipt"
    for field in result_type.model_fields:
        for carrier in ("bytes", "content", "payload", "document", "secret"):
            assert carrier not in field.lower(), f"{factory_name} result carries material: {field}"


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_no_executor_reaches_a_remote_surface(factory_name: str) -> None:
    """Live submission is prohibited, so no enrolment may transmit anywhere."""
    definition = _build(_definition_factories()[factory_name])
    source = inspect.getsource(definition.executor_factory.executor_type)
    tree = ast.parse(textwrap.dedent(source))
    reached = (
        {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        | {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        | {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    )

    for forbidden in ("submit", "httpx", "requests", "presentar", "upload"):
        assert not any(forbidden in name.lower() for name in reached), (
            f"{factory_name} reaches a remote surface: {forbidden}"
        )


def test_every_exported_definition_reaches_the_production_registry() -> None:
    """No enrolment ships as capacity nothing can reach.

    These definitions sat exported and uncomposed: the registry knew none of
    them, so no frontend could submit one and no journal could record one. A
    definition that cannot be reached is indistinguishable from one that does
    not exist, except that it still has to be maintained.
    """
    from ....entrypoints.operation_composition import build_production_operation_registry

    exported = {definition.definition_id for definition in _definitions().values()}
    composed = {definition.definition_id for definition in build_production_operation_registry().definitions}

    assert exported, "no enrolment is exported; this assertion would be vacuous"
    assert exported <= composed, f"exported but never composed: {sorted(exported - composed)}"
