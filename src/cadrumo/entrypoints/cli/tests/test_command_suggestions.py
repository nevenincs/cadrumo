"""Tests for the Cadrumo CLI command-suggestion group.

The base Typer group only suggests typo-distance near misses. These
tests cover the two operator-facing gaps :class:`CadrumoTyperGroup`
closes: a semantic synonym (``modify`` -> ``edit``) and a cross-path
command (``app status`` -> ``app overview status``).
"""

from __future__ import annotations

import pytest

from ....tests.cli_runner import invoke_cached_cli
from .. import app
from .._command_suggestions import walk_live_command_tree
from ._runtime_profile_cli_fixture import _isolated_cli_state

__all__ = ["_isolated_cli_state"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_profile_modify_suggests_edit() -> None:
    """``config profile modify`` suggests the canonical ``edit`` verb.

    The edit distance between ``modify`` and ``edit`` is too large for
    Typer's fuzzy matcher; the synonym table bridges the gap.
    """

    result = invoke_cached_cli(["config", "profile", "modify", "alice"])

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "modify" in flat
    assert "edit" in flat


def test_app_status_suggests_overview_status() -> None:
    """``app status`` suggests the cross-path ``app overview status``."""

    result = invoke_cached_cli(["app", "status"])

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "overview status" in flat


def test_unknown_command_with_no_synonym_still_fails_cleanly() -> None:
    """A genuinely unknown command with no synonym still fails without a trace."""

    result = invoke_cached_cli(["config", "profile", "zzzznonsense"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output


def test_live_command_walker_censuses_every_runtime_node_stably() -> None:
    """The census reaches deep lazy leaves and emits stable ownership."""
    first = walk_live_command_tree(app)
    second = walk_live_command_tree(app)

    assert first == second
    assert first == tuple(sorted(first, key=lambda node: node.path))
    assert len({node.path for node in first}) == len(first)
    assert first[0].path == ("aeat",)
    assert first[0].kind == "root"

    by_path = {node.path: node for node in first}
    assert by_path[("aeat", "config")].kind == "group"
    assert by_path[("aeat", "config", "profile", "delete")].kind == "leaf"
    assert by_path[("aeat", "app", "modelo", "work", "calculate")].kind == "leaf"
    assert all(node.handler_owner != "<none>" for node in first if node.kind == "leaf")
    assert any(node.loader_owner is not None for node in first)
    assert all(":" in node.loader_owner for node in first if node.loader_owner is not None)
    assert all(":" in node.handler_owner for node in first if node.handler_owner != "<none>")
