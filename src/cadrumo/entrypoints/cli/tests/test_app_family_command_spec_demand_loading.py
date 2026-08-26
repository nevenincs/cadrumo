"""Dynamic proofs that application families load only their CommandSpec surface."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_APP_FAMILIES = (
    "diagnostics",
    "ledger",
    "live",
    "modelo",
    "overview",
    "quickfile",
    "registry",
    "review",
)


@pytest.mark.parametrize("family", _APP_FAMILIES)
def test_app_family_help_is_graph_exact_and_imports_no_behavior_target(family: str) -> None:
    source = f"""
import json
import sys
from typer.testing import CliRunner
from cadrumo.entrypoints.cli import app
from cadrumo.entrypoints.cli.command_api import command_spec_nodes

nodes = command_spec_nodes()
families = {{node.path[2] for node in nodes if len(node.path) == 3 and node.path[:2] == ("aeat", "app")}}
family = {family!r}
family_path = ("aeat", "app", family)
descendants = tuple(node for node in nodes if node.path[:3] == family_path)
direct_children = tuple(sorted(node.path[-1] for node in descendants if len(node.path) == 4))
leaf = next((node for node in descendants if node.spec.kind == "leaf"), None)
handlers_by_family = {{
    owner: {{
        node.spec.handler.target.module
        for node in nodes
        if len(node.path) >= 3
        and node.path[:2] == ("aeat", "app")
        and node.path[2] == owner
        and node.spec.handler is not None
        and node.spec.handler.target is not None
    }}
    for owner in families
}}
all_handler_modules = {{
    node.spec.handler.target.module
    for node in nodes
    if len(node.path) >= 3
    and node.path[:2] == ("aeat", "app")
    and node.spec.handler is not None
    and node.spec.handler.target is not None
}}
already_loaded = set(sys.modules)
baseline_handlers = sorted(all_handler_modules.intersection(already_loaded))
runner = CliRunner()
family_help = runner.invoke(app, ["app", family, "--help"])
after_family_help = set(sys.modules)
leaf_help = None if leaf is None else runner.invoke(app, [*leaf.path[1:], "--help"])
after_leaf_help = set(sys.modules)
print(json.dumps({{
    "families": sorted(families),
    "direct_children": direct_children,
    "family_help": family_help.output,
    "family_exit": family_help.exit_code,
    "leaf_exit": None if leaf_help is None else leaf_help.exit_code,
    "baseline_handlers": baseline_handlers,
    "family_help_handlers": sorted(all_handler_modules.intersection(after_family_help - already_loaded)),
    "foreign_leaf_handlers": sorted(
        (all_handler_modules - handlers_by_family[family]).intersection(after_leaf_help - after_family_help)
    ),
}}))
"""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and authored test program
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert tuple(result["families"]) == _APP_FAMILIES
    assert result["family_exit"] == 0
    assert result["leaf_exit"] in {None, 0}
    assert all(token in result["family_help"] for token in result["direct_children"])
    assert result["baseline_handlers"] == []
    assert result["family_help_handlers"] == []
    assert result["foreign_leaf_handlers"] == []


def test_real_state_free_leaf_invocation_loads_only_its_own_family_behavior() -> None:
    source = """
import json
import sys
from typer.testing import CliRunner
from cadrumo.entrypoints.cli import app
from cadrumo.entrypoints.cli.command_api import command_spec_nodes

nodes = command_spec_nodes()
selected = next(node for node in nodes if node.path == ("aeat", "app", "live", "portals", "list"))
assert selected.spec.handler is not None and selected.spec.handler.target is not None
selected_handler = selected.spec.handler.target.module
handlers_by_family = {
    family: {
        node.spec.handler.target.module
        for node in nodes
        if len(node.path) >= 3
        and node.path[:2] == ("aeat", "app")
        and node.path[2] == family
        and node.spec.handler is not None
        and node.spec.handler.target is not None
    }
    for family in {node.path[2] for node in nodes if len(node.path) >= 3 and node.path[:2] == ("aeat", "app")}
}
already_loaded = set(sys.modules)
all_family_handlers = set().union(*handlers_by_family.values())
baseline_handlers = sorted(all_family_handlers.intersection(already_loaded))
result = CliRunner().invoke(app, ["--format", "json", "app", "live", "portals", "list"])
new_modules = set(sys.modules) - already_loaded
foreign_handlers = sorted(
    module
    for family, modules in handlers_by_family.items()
    if family != "live"
    for module in modules.intersection(new_modules)
)
print(json.dumps({
    "exit": result.exit_code,
    "command": json.loads(result.output)["command"] if result.exit_code == 0 else None,
    "selected_loaded": selected_handler in new_modules,
    "baseline_handlers": baseline_handlers,
    "foreign_handlers": foreign_handlers,
}))
"""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and authored test program
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result == {
        "exit": 0,
        "command": "app.live.portals.list",
        "selected_loaded": True,
        "baseline_handlers": [],
        "foreign_handlers": [],
    }
