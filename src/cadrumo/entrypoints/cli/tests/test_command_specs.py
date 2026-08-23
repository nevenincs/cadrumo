from __future__ import annotations

import ast
import json
import subprocess
import sys
from importlib.util import find_spec, resolve_name
from pathlib import Path

import pytest

from .._command_specs import COMMAND_GRAPH, COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_complete_command_authority_has_the_exact_shipped_shape() -> None:
    assert COMMAND_SPECS
    assert len(COMMAND_GRAPH.nodes()) == len(COMMAND_SPECS)
    assert sum(spec.kind == "root" for spec in COMMAND_SPECS) == 1
    assert all(spec.kind in {"root", "group", "leaf"} for spec in COMMAND_SPECS)
    assert len({node.path for node in COMMAND_GRAPH.nodes()}) == len(COMMAND_SPECS)


def test_every_executable_target_is_public_and_every_schema_identity_is_unique() -> None:
    executable = [spec for spec in COMMAND_SPECS if spec.handler is not None]
    assert executable
    assert all(spec.handler is not None and spec.handler.target is not None for spec in executable)
    assert all(
        not spec.handler.target.qualname.startswith("_")
        and ".<locals>." not in spec.handler.target.qualname
        for spec in executable
        if spec.handler is not None and spec.handler.target is not None
    )
    identities = [
        spec.result_schema.identity
        for spec in COMMAND_SPECS
        if spec.result_schema.identity is not None
    ]
    assert len(identities) == len(set(identities))


def test_complete_authority_import_does_not_import_behavior_modules() -> None:
    source = (
        "import json, sys; "
        "from cadrumo.entrypoints.cli._command_specs import COMMAND_SPECS; "
        "targets = {spec.result_schema.target.module for spec in COMMAND_SPECS "
        "if spec.result_schema.target is not None}; "
        "targets.update(spec.handler.target.module for spec in COMMAND_SPECS "
        "if spec.handler is not None and spec.handler.target is not None); "
        "loaded = sorted(targets.intersection(sys.modules)); "
        "print(json.dumps({'specs': len(COMMAND_SPECS), 'loaded': loaded}))"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and authored test program
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    observation = json.loads(completed.stdout)
    assert observation["specs"] == len(COMMAND_SPECS)
    assert observation["loaded"] == []


def test_handler_target_modules_do_not_import_the_cli_package_facade() -> None:
    modules = {
        spec.handler.target.module
        for spec in COMMAND_SPECS
        if spec.handler is not None and spec.handler.target is not None
    }
    facade = "cadrumo.entrypoints.cli"
    violations: list[str] = []
    for module in sorted(modules):
        found = find_spec(module)
        assert found is not None and found.origin is not None
        tree = ast.parse(Path(found.origin).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_module = node.module
                if node.level:
                    relative = f"{'.' * node.level}{node.module or ''}"
                    imported_module = resolve_name(relative, module.rpartition('.')[0])
                imported_names = {
                    imported_module if alias.name == "*" else f"{imported_module}.{alias.name}"
                    for alias in node.names
                    if imported_module is not None
                }
                if imported_module == facade or facade in imported_names:
                    violations.append(module)
            if isinstance(node, ast.Import) and any(alias.name == facade for alias in node.names):
                violations.append(module)
            if (
                isinstance(node, ast.Call)
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == facade
                and (
                    (isinstance(node.func, ast.Name) and node.func.id == "__import__")
                    or (isinstance(node.func, ast.Name) and node.func.id == "import_module")
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                )
            ):
                violations.append(module)
    assert violations == []
