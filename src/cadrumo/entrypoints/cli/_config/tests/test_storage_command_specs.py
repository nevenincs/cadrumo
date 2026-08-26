"""Storage command behavior is projected solely from production specs."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .._storage_command_specs import CONFIG_STORAGE_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_storage_spec_surface_and_parameter_contract_are_exact() -> None:
    by_token = {spec.token: spec for spec in CONFIG_STORAGE_COMMAND_SPECS}

    assert set(by_token) == {"storage", "list", "view", "check", "init", "reclaim"}
    assert by_token["storage"].parent_key == "config"
    assert by_token["storage"].handler is None
    assert tuple(parameter.name for parameter in by_token["view"].parameters) == (
        "area",
        "output_language",
    )
    assert tuple(parameter.name for parameter in by_token["reclaim"].parameters) == (
        "area",
        "confirmed",
        "output_language",
    )
    confirmed = by_token["reclaim"].parameters[1]
    assert confirmed.declarations == ("--yes",)
    assert confirmed.is_flag
    assert confirmed.flag_value is True


def test_storage_behavior_module_has_no_structural_cli_registration() -> None:
    source = Path(__file__).parents[1].joinpath("_storage_cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"command", "callback", "add_typer"}
        for node in ast.walk(tree)
    )
    assert "command_execution_policy" not in source
    assert "typer.Option" not in source
    assert "typer.Argument" not in source
