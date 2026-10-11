"""The Operations catalogue offers every registered operation, derived from the registry alone.

Nothing here names an operation the catalogue must contain: the expected set
is whatever the production registry publishes, so an operation registered
later is required here without this module changing.
"""

from __future__ import annotations

from functools import lru_cache

import pytest

from .....application.operations.registry import OperationRegistry
from .....application.operations.schema_identity import OperationSchemaIdentityV1
from ....operation_composition import build_production_operation_registry
from ..catalogue import OperationCatalogueSourceV1, OperationCatalogueV1, build_operation_catalogue
from ..destination import OPERATION_FOCUS_KEY, OPERATIONS_DESTINATION
from ..palette import operation_navigation_target

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@lru_cache(maxsize=1)
def _registry() -> OperationRegistry:
    return build_production_operation_registry()


@lru_cache(maxsize=1)
def _catalogue() -> OperationCatalogueV1:
    return build_operation_catalogue(_registry())


def test_every_registered_operation_is_offered() -> None:
    registered = [contract.definition_id for contract in _registry().public_contract_set.definitions]

    offered = [entry.definition_id for entry in _catalogue().entries]

    assert offered == registered
    assert len(offered) > 200


def test_every_entry_carries_the_registered_contract_and_its_own_input_model() -> None:
    registry = _registry()

    for entry in _catalogue().entries:
        definition = registry.lookup(entry.definition_id)
        assert entry.contract == registry.lookup_public_contract(entry.definition_id)
        registered_result = entry.contract.result_schema
        if registered_result is None:
            assert entry.result_type is None
        else:
            assert entry.result_type is registry.lookup_public_schema_binding(registered_result).model_type
            assert registered_result == OperationSchemaIdentityV1.from_model(
                schema_id=registered_result.schema_id,
                schema_version=registered_result.schema_version,
                model_type=entry.result_type,
            )
        assert entry.typed_operator_input == (entry.contract.transient_financial_operand is not None)
        if not entry.typed_operator_input:
            assert entry.input_type is definition.request_type
            described = registry.describe_public_definition(entry.definition_id)
            assert entry.input_json_schema == described.request_json_schema


def test_an_operation_with_a_typed_operator_input_is_entered_as_that_input() -> None:
    typed = [entry for entry in _catalogue().entries if entry.typed_operator_input]

    assert typed
    for entry in typed:
        assert entry.input_type is not _registry().lookup(entry.definition_id).request_type
        assert "submission" in entry.input_type.model_fields


def test_grouping_places_every_operation_under_exactly_one_family() -> None:
    catalogue = _catalogue()

    grouped = catalogue.grouped()

    families = [family for family, _entries in grouped]
    assert families == sorted(set(families))
    listed = [entry.definition_id for _family, entries in grouped for entry in entries]
    assert sorted(listed) == [entry.definition_id for entry in catalogue.entries]
    assert all(entry.family == family for family, entries in grouped for entry in entries)


def test_search_finds_an_operation_by_its_identifier_and_by_its_description() -> None:
    catalogue = _catalogue()
    described = next(entry for entry in catalogue.entries if entry.summary)
    word = max(described.summary.split(), key=len)

    assert [entry.definition_id for entry in catalogue.search(described.definition_id)] == [described.definition_id]
    assert described in catalogue.search(word.upper())
    assert catalogue.search("no-registered-operation-is-called-this") == ()
    assert catalogue.search("") == catalogue.entries


def test_every_operation_has_its_own_navigation_target() -> None:
    catalogue = _catalogue()

    tokens = {entry.focus_token for entry in catalogue.entries}

    assert len(tokens) == len(catalogue.entries)
    for entry in catalogue.entries:
        target = operation_navigation_target(entry)
        assert target.destination == OPERATIONS_DESTINATION
        assert target.focus.semantic_key == OPERATION_FOCUS_KEY
        assert target.focus.restore_token is not None
        assert catalogue.entry_for_token(target.focus.restore_token) is entry


def test_the_catalogue_is_composed_once_however_often_it_is_read() -> None:
    compositions: list[int] = []

    def registry() -> OperationRegistry:
        compositions.append(1)
        return _registry()

    source = OperationCatalogueSourceV1(registry)

    assert compositions == []
    first = source.load()
    assert source.load() is first
    assert compositions == [1]
