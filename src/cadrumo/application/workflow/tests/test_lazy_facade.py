"""Import and public-surface contracts for the workflow facade."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _isolated_modules(expression: str) -> list[str]:
    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned expression
        [sys.executable, "-c", expression],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, list):
        raise TypeError("the isolated import probe must return a JSON list")
    loaded: list[str] = []
    for value in payload:
        if not isinstance(value, str):
            raise TypeError("the isolated import probe must return module names")
        loaded.append(value)
    return loaded


def _canonical_owner_path(module_path: str, *, package: str) -> str:
    """Resolve a source-level relative owner path without importing it."""
    level = len(module_path) - len(module_path.lstrip("."))
    if level == 0:
        return module_path
    package_parts = package.split(".")
    retained = len(package_parts) - level + 1
    if retained <= 0:
        raise ValueError(f"owner path {module_path!r} escapes package {package!r}")
    suffix = module_path[level:]
    return ".".join((*package_parts[:retained], suffix)) if suffix else ".".join(package_parts[:retained])


def test_importing_workflow_facade_loads_no_owning_submodule() -> None:
    loaded = _isolated_modules(
        "import json, sys; import cadrumo.application.workflow; "
        "print(json.dumps(sorted(name for name in sys.modules "
        "if name.startswith('cadrumo.application.workflow.'))))"
    )

    assert loaded == []


def test_lazy_map_has_exact_public_name_parity() -> None:
    from ... import workflow

    assert set(workflow._LAZY_EXPORTS) == set(workflow.__all__)
    assert set(workflow.__all__).issubset(dir(workflow))


def test_lazy_public_names_have_exact_static_owner_bindings() -> None:
    """Static imports mirror the runtime owners without loading them at runtime."""
    from ... import workflow

    facade_tree = ast.parse(Path(workflow.__file__).read_text(encoding="utf-8"))
    type_checking_block = next(
        statement
        for statement in facade_tree.body
        if isinstance(statement, ast.If)
        and isinstance(statement.test, ast.Name)
        and statement.test.id == "TYPE_CHECKING"
    )
    static_owners = {
        alias.asname or alias.name: _canonical_owner_path(
            "." * statement.level + (statement.module or ""),
            package=workflow.__name__,
        )
        for statement in type_checking_block.body
        if isinstance(statement, ast.ImportFrom)
        for alias in statement.names
    }
    runtime_owners = {
        name: _canonical_owner_path(module_path, package=workflow.__name__)
        for name, module_path in workflow._LAZY_EXPORTS.items()
    }

    assert static_owners == runtime_owners


def test_each_public_name_resolves_from_its_declared_owner() -> None:
    from ... import workflow

    for name, module_path in workflow._LAZY_EXPORTS.items():
        value = getattr(workflow, name)
        owner = workflow._LAZY_MODULE_LOADERS[module_path]()
        assert value is getattr(owner, name)
