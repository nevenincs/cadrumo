"""Each surface name stands for one exact tool list and one pair of properties.

A client that pins a surface name relies on what the name stood for when it
pinned it. The table here records that for every name, tool by tool, and the
live surfaces are held to it. A surface that gains or loses a tool, or changes
one of its two properties, fails here: it takes a new name with a row of its
own, and the row of a name still served stays as it is.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

import pytest

from ..mcp_surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface, McpSurfaceName

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True, slots=True)
class _Pin:
    """What one surface name stands for."""

    tools: tuple[str, ...]
    changes_records: bool
    reaches_network: bool


_PINNED: Mapping[str, _Pin] = {
    "full": _Pin(
        tools=(
            "authority",
            "control",
            "corpus_search",
            "describe",
            "execute",
            "observe",
            "respond",
            "result",
            "result_page",
            "review",
            "search",
            "status",
        ),
        changes_records=True,
        reaches_network=True,
    ),
    "read-only-local": _Pin(
        tools=(
            "authority",
            "control",
            "corpus_search",
            "describe",
            "execute",
            "observe",
            "result",
            "result_page",
            "search",
            "status",
        ),
        changes_records=False,
        reaches_network=False,
    ),
}
"""Every surface name with the tools it advertises, in order, and its two declared properties."""

_RENAME = "a surface whose tools or properties change takes a new name, with a row of its own"


def _finding(surface: McpSurface, pinned: Mapping[str, _Pin]) -> str | None:
    """Say how one live surface departs from what its name is pinned to, when it does."""
    pin = pinned.get(surface.name.value)
    if pin is None:
        return "is served under a name with no pinned tool list"
    gained = sorted(surface.tools - set(pin.tools))
    lost = sorted(set(pin.tools) - surface.tools)
    if gained or lost:
        return f"gained {gained} and lost {lost} under its pinned name"
    if (surface.changes_records, surface.reaches_network) != (pin.changes_records, pin.reaches_network):
        return "declares other properties than its pinned name stands for"
    return None


def test_every_served_surface_advertises_exactly_the_tools_and_properties_its_name_is_pinned_to() -> None:
    findings = {
        surface.name.value: finding
        for surface in MCP_SURFACES.values()
        if (finding := _finding(surface, _PINNED)) is not None
    }
    assert not findings, f"{findings}; {_RENAME}"


def test_every_pinned_name_is_served_and_spelled_once_in_order() -> None:
    assert set(_PINNED) == {name.value for name in McpSurfaceName} == {name.value for name in MCP_SURFACES}
    for name, pin in _PINNED.items():
        assert list(pin.tools) == sorted(set(pin.tools)), f"{name}: the pinned tools are listed once, in order"


def test_the_default_surface_is_the_one_that_keeps_everything_and_advertises_every_tool() -> None:
    default = MCP_SURFACES[DEFAULT_MCP_SURFACE]

    assert not default.narrows
    assert (default.changes_records, default.reaches_network, default.operations) == (True, True, None)
    every_tool = frozenset[str]().union(*(surface.tools for surface in MCP_SURFACES.values()))
    assert default.tools == every_tool, "the default is the newest surface that keeps everything"


def test_a_surface_that_changes_under_its_name_is_found() -> None:
    full = MCP_SURFACES[McpSurfaceName.FULL]
    narrowed = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]

    assert _finding(full, _PINNED) is None
    assert _finding(replace(full, tools=full.tools | {"another_tool"}), _PINNED) is not None
    assert _finding(replace(full, tools=full.tools - {"status"}), _PINNED) is not None
    assert _finding(replace(narrowed, reaches_network=True), _PINNED) is not None
    assert _finding(replace(narrowed, changes_records=True, operations=None), _PINNED) is not None
    assert _finding(full, {"read-only-local": _PINNED["read-only-local"]}) is not None
