"""The contract generator takes the environment contract from the package declaration, never from the CLI."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE = Path(__file__).resolve().parents[1]
_PACKAGE_NAME = "dev.packaging.native"

# Inputs that describe the product or its runtime protocol rather than any process environment.
_NON_ENVIRONMENT_INPUTS = frozenset(
    {
        "cadrumo.core.product_identity",
        "cadrumo.core.connection_transport",
        "cadrumo_client.contracts.contracts",
        "dev._paths",
        "dev.locales.manager_chrome",
        "dev.packaging.runtime_wheelhouse_contract",
    }
)


def _imports(source: str, package: str) -> set[str]:
    """Return every module a source imports, with relative imports resolved against ``package``."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                base = f"{parent}.{base}" if base else parent
                if node.module is None:
                    modules.update(f"{base}.{alias.name}" for alias in node.names)
                    continue
            # ``from package import module`` names the module, not the package.
            submodules = {f"{base}.{alias.name}" for alias in node.names if _is_module(f"{base}.{alias.name}")}
            modules.update(submodules or {base})
    return modules


def _is_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def _generator_closure() -> dict[str, set[str]]:
    """Map each generator module, followed through its in-package imports, to what it imports."""
    pending: list[str] = [f"{_PACKAGE_NAME}.generate"]
    seen: dict[str, set[str]] = {}
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        path = _PACKAGE / f"{module.removeprefix(_PACKAGE_NAME + '.')}.py"
        seen[module] = _imports(path.read_text(encoding="utf-8"), _PACKAGE_NAME)
        pending.extend(name for name in seen[module] if name.startswith(_PACKAGE_NAME + ".") and name not in seen)
    return seen


def _outside_imports(closure: dict[str, set[str]]) -> set[str]:
    return {
        name
        for imported in closure.values()
        for name in imported
        if name.split(".")[0]
        in {"cadrumo", "cadrumo_client", "cadrumo_runtime", "cadrumo_harness", "cadrumo_agent_service", "dev"}
        and not name.startswith(_PACKAGE_NAME + ".")
    }


def test_the_generator_imports_no_cadrumo_environment_declaration() -> None:
    closure = _generator_closure()
    assert f"{_PACKAGE_NAME}.application_environment" in closure
    assert f"{_PACKAGE_NAME}.storage_vectors" in closure
    assert _outside_imports(closure) <= _NON_ENVIRONMENT_INPUTS


def test_the_import_check_detects_a_planted_cli_declaration() -> None:
    planted = (
        "from cadrumo.core.config import Settings\n"
        "from cadrumo.core.storage_environment import STORAGE_ROOT\n"
        "from .layout import load_layout\n"
    )
    imported = _imports(planted, _PACKAGE_NAME)
    assert imported == {"cadrumo.core.config", "cadrumo.core.storage_environment", f"{_PACKAGE_NAME}.layout"}
    assert _outside_imports({"planted": imported}) - _NON_ENVIRONMENT_INPUTS == {
        "cadrumo.core.config",
        "cadrumo.core.storage_environment",
    }
