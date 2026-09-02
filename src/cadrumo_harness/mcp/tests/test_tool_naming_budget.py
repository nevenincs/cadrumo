"""Every prefixed MCP tool name fits the client budget.

A Claude plugin prepends ``mcp__plugin_<plugin>_<server>__`` to every tool name;
with the plugin and server both named ``cadrumo`` that prefix is 29 characters, so a
long command key can push the client-visible name past the practical 64-char
ceiling. This gate asserts every exposed command's prefixed name is within budget
(declared short forms shrink the few that would overflow), that the short forms
keep names unique and reversible, and that no new deep verb path can silently
reintroduce an over-budget name.
"""

from __future__ import annotations

import pytest

from .._dispatch import (
    TOOL_NAME_BUDGET,
    command_key_for_tool,
    prefixed_tool_name_length,
    tool_name_for_command,
)
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _exposable_keys() -> list[str]:
    return [descriptor.command_key for descriptor in build_tool_descriptors()]


def test_every_prefixed_tool_name_is_within_budget() -> None:
    over = [key for key in _exposable_keys() if prefixed_tool_name_length(key) > TOOL_NAME_BUDGET]
    assert over == [], f"tool names over the {TOOL_NAME_BUDGET}-char client budget: {over}"


def test_tool_names_stay_unique_after_abbreviation() -> None:
    keys = _exposable_keys()
    names = [tool_name_for_command(key) for key in keys]
    assert len(set(names)) == len(names)


def test_abbreviated_names_reverse_to_their_command_key() -> None:
    keys = _exposable_keys()
    # Every forward name resolves back to its own key through the shared resolver,
    # including the abbreviated ones (the resolver matches on the forward mapping).
    for key in keys:
        name = tool_name_for_command(key)
        assert command_key_for_tool(name, command_keys=keys) == key


def test_a_hypothetical_deep_verb_would_trip_the_budget_gate() -> None:
    # Anti-tautology: a synthetic very-deep command key with no abbreviation
    # overflows the budget, proving the gate has teeth.
    # The key is deliberately not a registered command: exposability is decided by
    # the live command graph, so only the budget arithmetic can be proven here.
    deep = "modelo.work.some_very_long_new_subcommand_that_would_overflow_the_budget"
    assert prefixed_tool_name_length(deep) > TOOL_NAME_BUDGET
    assert prefixed_tool_name_length("modelo.work.calculate") <= TOOL_NAME_BUDGET
