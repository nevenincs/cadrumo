"""The named MCP surfaces keep the shape their readers and their runtime rely on."""

from __future__ import annotations

import pytest

from ..mcp_surface_facts import OPERATION_SURFACE_FACTS, operation_surface_facts
from ..mcp_surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface, McpSurfaceName, mcp_surface

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNRECORDED = "domain.thing.unrecorded"


def _recorded(*, changes_records: bool, reaches_network: bool) -> str:
    """Name one recorded operation with exactly these two facts."""
    return next(
        facts.definition_id
        for facts in OPERATION_SURFACE_FACTS
        if facts.changes_records is changes_records and facts.reaches_network is reaches_network
    )


def _surface(*, changes_records: bool, reaches_network: bool, operations: frozenset[str] | None = None) -> McpSurface:
    return McpSurface(
        name=McpSurfaceName.READ_ONLY_LOCAL,
        tools=frozenset({"status"}),
        changes_records=changes_records,
        reaches_network=reaches_network,
        operations=operations,
    )


def test_the_names_a_client_pins_are_the_two_served_surfaces() -> None:
    assert {name.value for name in McpSurfaceName} == {"full", "read-only-local"}
    assert set(MCP_SURFACES) == set(McpSurfaceName)
    for name, surface in MCP_SURFACES.items():
        assert surface.name is name
        assert mcp_surface(name.value) is surface


def test_an_unknown_surface_name_is_refused() -> None:
    for unknown in ("", "read-only", "Full", "read_only_local"):
        with pytest.raises(KeyError, match="unknown MCP surface"):
            mcp_surface(unknown)


def test_the_default_surface_narrows_nothing() -> None:
    surface = MCP_SURFACES[DEFAULT_MCP_SURFACE]

    assert surface.name is McpSurfaceName.FULL
    assert surface.changes_records and surface.reaches_network
    assert surface.operations is None
    assert not surface.narrows
    for facts in OPERATION_SURFACE_FACTS:
        assert surface.admits(facts.definition_id)
    assert surface.admits(_UNRECORDED)


def test_the_read_only_local_surface_declares_and_lists_exactly_the_local_reads() -> None:
    surface = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
    local_reads = {
        facts.definition_id
        for facts in OPERATION_SURFACE_FACTS
        if not facts.changes_records and not facts.reaches_network
    }

    assert not surface.changes_records and not surface.reaches_network
    assert surface.narrows
    assert surface.operations
    assert surface.operations == local_reads
    for definition_id in sorted(surface.operations):
        facts = operation_surface_facts(definition_id)
        assert not facts.changes_records, definition_id
        assert not facts.reaches_network, definition_id
        assert surface.admits(definition_id), definition_id


def test_the_read_only_local_surface_admits_no_recorded_write_and_no_recorded_network_reach() -> None:
    surface = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
    barred = [facts for facts in OPERATION_SURFACE_FACTS if facts.changes_records or facts.reaches_network]

    assert barred
    assert not [facts.definition_id for facts in barred if surface.admits(facts.definition_id)]
    assert not surface.admits(_UNRECORDED)


def test_each_declared_property_is_applied_on_its_own() -> None:
    local_write = _recorded(changes_records=True, reaches_network=False)
    online_write = _recorded(changes_records=True, reaches_network=True)
    local_read = _recorded(changes_records=False, reaches_network=False)
    local_only = _surface(changes_records=True, reaches_network=False)
    read_only = _surface(changes_records=False, reaches_network=True)

    assert local_only.narrows and read_only.narrows
    assert local_only.admits(local_write) and local_only.admits(local_read)
    assert not local_only.admits(online_write)
    assert read_only.admits(local_read)
    assert not read_only.admits(local_write) and not read_only.admits(online_write)
    assert not local_only.admits(_UNRECORDED) and not read_only.admits(_UNRECORDED)


def test_an_operation_list_narrows_within_the_declared_properties() -> None:
    kept = _recorded(changes_records=False, reaches_network=False)
    other = next(
        facts.definition_id
        for facts in OPERATION_SURFACE_FACTS
        if not facts.changes_records and not facts.reaches_network and facts.definition_id != kept
    )
    listed = _surface(changes_records=True, reaches_network=True, operations=frozenset({kept}))

    assert listed.narrows
    assert listed.admits(kept)
    assert not listed.admits(other)


def test_a_surface_cannot_list_an_operation_outside_its_declared_properties() -> None:
    local_write = _recorded(changes_records=True, reaches_network=False)
    online_write = _recorded(changes_records=True, reaches_network=True)

    with pytest.raises(ValueError, match="outside the surface's declared properties"):
        _surface(changes_records=False, reaches_network=False, operations=frozenset({local_write}))
    with pytest.raises(ValueError, match="outside the surface's declared properties"):
        _surface(changes_records=True, reaches_network=False, operations=frozenset({online_write}))
    with pytest.raises(ValueError, match="outside the surface's declared properties"):
        _surface(changes_records=True, reaches_network=True, operations=frozenset({_UNRECORDED}))


def test_a_surface_advertises_at_least_one_tool() -> None:
    with pytest.raises(ValueError, match="at least one tool"):
        McpSurface(
            name=McpSurfaceName.FULL, tools=frozenset(), changes_records=True, reaches_network=True, operations=None
        )
