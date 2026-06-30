"""Tests for the MCP tool descriptors and the name/argv dispatch mapping."""

from __future__ import annotations

import pytest

from .._dispatch import command_key_for_tool, tool_name_for_command, tool_request_argv
from .._tools import build_tool_descriptors

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


def test_argv_places_format_json_at_root_and_keeps_args() -> None:
    assert tool_request_argv("modelo.work.calculate", ["wu_123"]) == [
        "--format",
        "json",
        "app",
        "modelo",
        "work",
        "calculate",
        "wu_123",
    ]
    # config and app.live keys carry their own leading root segment.
    assert tool_request_argv("config.profile.create", ["acme"]) == [
        "--format",
        "json",
        "config",
        "profile",
        "create",
        "acme",
    ]
    assert tool_request_argv("app.live.filed.pull", [])[2:4] == ["app", "live"]
