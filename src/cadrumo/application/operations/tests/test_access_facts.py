"""The recorded access facts keep a shape their readers can rely on."""

from __future__ import annotations

import pytest

from ..access_facts import OPERATION_ACCESS_FACTS, operation_access_facts
from ..person_acts import operation_is_persons_act

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_facts_are_unique_and_sorted_by_definition_id() -> None:
    identifiers = [facts.definition_id for facts in OPERATION_ACCESS_FACTS]

    assert identifiers == sorted(set(identifiers))


def test_lookup_returns_the_recorded_facts_and_refuses_an_unrecorded_operation() -> None:
    for facts in OPERATION_ACCESS_FACTS:
        assert operation_access_facts(facts.definition_id) is facts

    with pytest.raises(KeyError, match="no recorded access facts"):
        operation_access_facts("domain.thing.unrecorded")


def test_every_combination_of_the_two_facts_is_recorded_for_some_operation() -> None:
    """Access scopes and MCP surfaces are derived from both facts, so each must tell operations apart."""
    recorded = {(facts.changes_records, facts.reaches_network) for facts in OPERATION_ACCESS_FACTS}

    assert recorded == {(False, False), (False, True), (True, False), (True, True)}


def test_the_setup_operations_are_recorded_and_the_removed_operations_are_not() -> None:
    """Setup is not a person's act, so its facts decide what a narrowed scope admits."""
    for definition_id in ("dependencies.status", "dependencies.verify", "dependencies.setup"):
        assert not operation_is_persons_act(definition_id, ephemeral_secret_required=False)
    assert operation_access_facts("dependencies.setup").changes_records
    assert operation_access_facts("dependencies.setup").reaches_network
    assert not operation_access_facts("dependencies.status").changes_records
    assert not operation_access_facts("dependencies.verify").changes_records
    for removed in ("browser-runtime.provision", "provider-settings.status", "provider-settings.set"):
        with pytest.raises(KeyError):
            operation_access_facts(removed)
