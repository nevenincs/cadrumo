"""Profile inventory/readiness leaves are declared by production specs."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .._profile_inventory_specs import PROFILE_INVENTORY_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_profile_inventory_specs_preserve_paths_handlers_and_language_option() -> None:
    assert {(spec.parent_key, spec.token) for spec in PROFILE_INVENTORY_COMMAND_SPECS} == {
        ("config_profile", "list"),
        ("config_profile", "status"),
    }
    for spec in PROFILE_INVENTORY_COMMAND_SPECS:
        assert spec.handler is not None
        assert spec.handler.target is not None
        assert spec.invocation.context_parameter == "ctx"
        assert len(spec.parameters) == 1
        option = spec.parameters[0]
        assert option.name == "output_language"
        assert option.declarations == ("--output-language", "--language")


@pytest.mark.parametrize("module_name", ["_profile_list_cli.py", "_profile_status_cli.py"])
def test_profile_inventory_handlers_own_no_typer_registration_metadata(module_name: str) -> None:
    source = Path(__file__).parents[1].joinpath(module_name).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"command", "callback"}
        for node in ast.walk(tree)
    )
    assert "command_execution_policy" not in source
    assert "typer.Option" not in source
