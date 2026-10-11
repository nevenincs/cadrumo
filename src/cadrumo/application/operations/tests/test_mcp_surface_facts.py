"""The recorded surface facts keep a shape their readers can rely on."""

from __future__ import annotations

import pytest

from ..mcp_surface_facts import OPERATION_SURFACE_FACTS, operation_surface_facts

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
