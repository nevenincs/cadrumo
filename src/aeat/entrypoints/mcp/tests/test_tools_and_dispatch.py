"""Tests for the MCP tool descriptors and the name/argv dispatch mapping."""

from __future__ import annotations

import pytest

from .._annotations import annotation_coverage_gaps
from .._dispatch import command_key_for_tool, tool_name_for_command
from .._input_schema import cli_argv_for
from .._tools import build_tool_descriptors
from .._toolsets import Toolset, build_toolsets

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_exposable_command_has_a_descriptor() -> None:
    descriptors = build_tool_descriptors()
    assert len(descriptors) >= 200
    # Group-callback help surfaces are not operator-callable tools.
    keys = {d.command_key for d in descriptors}
    assert "root.status" not in keys
    assert "root.app" not in keys
    assert "contract" in keys
    assert "modelo.work.calculate" in keys


def test_descriptors_are_well_formed() -> None:
    for descriptor in build_tool_descriptors():
        assert descriptor.name.startswith("aeat_")
        assert descriptor.description
        assert descriptor.input_schema["type"] == "object"
        assert descriptor.output_schema  # the registered result model schema
        assert descriptor.annotations.title


def test_every_descriptor_carries_a_per_verb_schema_not_the_args_bag() -> None:
    for descriptor in build_tool_descriptors():
        # The retired ``{args: [string]}`` bag must not survive anywhere.
        assert "args" not in descriptor.input_schema["properties"]
        # The rendered schema is exactly the structured verb schema's projection.
        assert descriptor.input_schema == descriptor.verb_schema.json_schema()
        assert descriptor.verb_schema.command_key == descriptor.command_key


def test_mutability_projects_onto_annotations() -> None:
    by_key = {d.command_key: d for d in build_tool_descriptors()}
    assert by_key["contract"].annotations.read_only_hint is True
    assert by_key["overview.status"].annotations.read_only_hint is True
    assert by_key["ledger.add"].annotations.read_only_hint is False
    assert by_key["ledger.remove"].annotations.destructive_hint is True
    assert by_key["ledger.add"].annotations.destructive_hint is False


def test_tool_name_round_trips_including_segment_underscores() -> None:
    keys = [d.command_key for d in build_tool_descriptors()]
    # iva_wallet has a segment-internal underscore; the round-trip must be exact.
    name = tool_name_for_command("modelo.iva_wallet.balance")
    assert name == "aeat_modelo_iva_wallet_balance"
    assert command_key_for_tool(name, command_keys=keys) == "modelo.iva_wallet.balance"
    assert command_key_for_tool("aeat_not_a_real_tool", command_keys=keys) is None


def test_descriptor_argv_places_format_json_at_root_and_maps_named_arguments() -> None:
    by_key = {d.command_key: d for d in build_tool_descriptors()}
    calculate = by_key["modelo.work.calculate"].verb_schema
    assert cli_argv_for(calculate, {"work_unit_id": "wu_123"}) == [
        "--format",
        "json",
        "app",
        "modelo",
        "work",
        "calculate",
        "wu_123",
    ]
    # config keys carry their own leading root segment.
    create = by_key["config.profile.create"].verb_schema
    assert cli_argv_for(create, {"profile_name": "acme"}) == [
        "--format",
        "json",
        "config",
        "profile",
        "create",
        "acme",
    ]
    # The resolved path uses the hyphenated command name click dispatches on.
    pull = by_key["app.live.iva_wallet.pull"].verb_schema
    assert cli_argv_for(pull, {})[2:5] == ["app", "live", "iva-wallet"]


def test_annotation_coverage_is_total_over_the_descriptor_set() -> None:
    descriptors = build_tool_descriptors()
    gaps = annotation_coverage_gaps((descriptor.command_key, descriptor.annotations) for descriptor in descriptors)
    assert gaps == ()


def test_toolset_membership_derives_from_the_live_descriptor_set() -> None:
    descriptor_keys = {descriptor.command_key for descriptor in build_tool_descriptors()}
    groups = build_toolsets()
    # Every toolset is one of the five curated domains and non-empty.
    assert {group.toolset for group in groups} == set(Toolset)
    for group in groups:
        assert group.command_keys, f"toolset {group.toolset} is empty"
        # Every grouped command is a real exposed descriptor - the toolsets
        # derive from the live surface, never a hand-listed set that could drift.
        assert set(group.command_keys) <= descriptor_keys
