"""The recorded surface facts keep a shape their readers can rely on."""

from __future__ import annotations

import pytest

from ..surface_facts import OPERATION_SURFACE_FACTS, operation_surface_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_facts_are_unique_and_sorted_by_definition_id() -> None:
    identifiers = [facts.definition_id for facts in OPERATION_SURFACE_FACTS]

    assert identifiers == sorted(set(identifiers))


def test_lookup_returns_the_recorded_facts_and_refuses_an_unrecorded_operation() -> None:
    for facts in OPERATION_SURFACE_FACTS:
        assert operation_surface_facts(facts.definition_id) is facts

    with pytest.raises(KeyError, match="no recorded surface facts"):
        operation_surface_facts("domain.thing.unrecorded")


def test_every_combination_of_the_two_facts_is_recorded_for_some_operation() -> None:
    """The surfaces are derived from both facts, so each must tell operations apart."""
    recorded = {(facts.changes_records, facts.reaches_network) for facts in OPERATION_SURFACE_FACTS}

    assert recorded == {(False, False), (False, True), (True, False), (True, True)}


def test_the_setup_operations_are_served_on_mcp_and_the_removed_browser_operation_is_not_recorded() -> None:
    """MCP refuses nothing the CLI can do: setup is not a person's act, and its facts are recorded."""
    from cadrumo.application.operations.person_acts import operation_is_persons_act

    for definition_id in ("dependencies.status", "dependencies.verify", "dependencies.setup"):
        assert not operation_is_persons_act(definition_id, ephemeral_secret_required=False)
    assert operation_surface_facts("dependencies.setup").changes_records
    assert operation_surface_facts("dependencies.setup").reaches_network
    assert not operation_surface_facts("dependencies.status").changes_records
    assert not operation_surface_facts("dependencies.verify").changes_records
    with pytest.raises(KeyError):
        operation_surface_facts("browser-runtime.provision")
