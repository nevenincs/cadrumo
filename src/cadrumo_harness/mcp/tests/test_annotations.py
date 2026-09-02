"""Tests for the MCP tool annotation coverage contract.

Exercised against the live tool descriptors - no mocks - so annotation coverage
is proven over the real command surface, plus unit checks on the coverage
predicate itself.
"""

from __future__ import annotations

import importlib.util

import pytest

from cadrumo.entrypoints.cli import command_execution_policy_for_cli_path

from .._annotations import (
    McpAnnotations,
    annotation_coverage_gaps,
    annotations_are_covered,
)
from .._hitl import (
    REQUIRES_USER_INTERACTION_META_KEY,
    ConfirmationPolicy,
    confirmation_for_tool,
    requires_user_interaction,
)
from .._server import build_sdk_tools
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_descriptor_has_full_annotation_coverage() -> None:
    descriptors = build_tool_descriptors()
    gaps = annotation_coverage_gaps((descriptor.command_key, descriptor.annotations) for descriptor in descriptors)
    assert gaps == ()


def test_open_world_hint_covers_exactly_the_sede_family_over_the_real_surface() -> None:
    # openWorldHint follows the attached policy's network capability, never a
    # key/path naming heuristic.
    descriptors = build_tool_descriptors()
    for descriptor in descriptors:
        raw = command_execution_policy_for_cli_path(descriptor.verb_schema.cli_path)
        expected = "network" in raw.classification.expanded_capabilities
        assert descriptor.annotations.open_world_hint is expected, descriptor.command_key
    assert any(descriptor.annotations.open_world_hint for descriptor in descriptors)


def test_classification_backs_both_the_annotation_and_the_confirmation_tier() -> None:
    # The client hint and the server gate read one authority (H3): a destructive
    # verb is destructive-hinted AND its confirmation tier is CONFIRM.
    descriptors = build_tool_descriptors()
    by_key = {descriptor.command_key: descriptor for descriptor in descriptors}
    remove = by_key.get("ledger.remove")
    assert remove is not None
    assert remove.annotations.destructive_hint is True
    assert confirmation_for_tool(command_key="ledger.remove") is ConfirmationPolicy.CONFIRM


def test_a_read_only_and_destructive_annotation_is_a_gap() -> None:
    contradictory = McpAnnotations(
        title="x",
        read_only_hint=True,
        destructive_hint=True,
        idempotent_hint=True,
    )
    assert annotations_are_covered(contradictory) is False
    assert annotation_coverage_gaps([("some.command", contradictory)]) == ("some.command",)


def test_a_read_only_non_idempotent_annotation_is_a_gap() -> None:
    non_idempotent_read = McpAnnotations(
        title="x",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=False,
    )
    assert annotations_are_covered(non_idempotent_read) is False


def test_a_non_destructive_mutating_annotation_is_covered() -> None:
    mutating = McpAnnotations(
        title="x",
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    )
    assert annotations_are_covered(mutating) is True
    assert annotation_coverage_gaps([("ledger.add", mutating)]) == ()


def test_requires_user_interaction_is_the_confirm_tier_exactly() -> None:
    assert requires_user_interaction(ConfirmationPolicy.CONFIRM) is True
    assert requires_user_interaction(ConfirmationPolicy.AUTO_APPROVE) is False
    assert requires_user_interaction(ConfirmationPolicy.BLOCK) is False


def _confirm_tier_command_keys() -> frozenset[str]:
    """The live command keys the confirmation gate classifies as CONFIRM.

    Computed from :func:`confirmation_for_tool` over the real descriptors, so the
    expected ``requiresUserInteraction`` set is derived from the same classification
    the server enforces, never a hand-maintained list.
    """
    return frozenset(
        descriptor.command_key
        for descriptor in build_tool_descriptors()
        if confirmation_for_tool(command_key=descriptor.command_key) is ConfirmationPolicy.CONFIRM
    )


def test_requires_user_interaction_meta_marks_exactly_the_confirm_tier_tools() -> None:
    descriptors = build_tool_descriptors()
    if importlib.util.find_spec("mcp") is None:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_sdk_tools(descriptors)
        return

    confirm_keys = _confirm_tier_command_keys()
    assert confirm_keys, "the live surface must expose at least one CONFIRM-tier tool"

    tools_by_command = {descriptor.command_key: descriptor.name for descriptor in descriptors}
    sdk_by_name = {tool.name: tool for tool in build_sdk_tools(descriptors)}

    for descriptor in descriptors:
        tool = sdk_by_name[tools_by_command[descriptor.command_key]]
        carries_flag = (tool.meta or {}).get(REQUIRES_USER_INTERACTION_META_KEY) is True
        # The flag is present iff the tool is CONFIRM tier: any new tool that enters
        # the CONFIRM tier joins ``confirm_keys`` and is stamped automatically.
        assert carries_flag is (descriptor.command_key in confirm_keys)
        # Read-only tools are never a confirmation subject, so never carry the flag.
        if descriptor.annotations.read_only_hint:
            assert carries_flag is False
