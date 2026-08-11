"""Structural contract for the explicit M303 simplified-regime scope input."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from .. import build_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_ROOT = Path("src")
_PACKAGE_ROOT = _SOURCE_ROOT / "cadrumo"
_BUILDER_MODULE = "cadrumo.application.filing"
_SCOPE_KEYWORD = "m303_regimen_simplificado_scope"


def _resolved_import_module(path: Path, node: ast.ImportFrom) -> str:
    """Resolve an import-from target relative to its importing package."""
    if node.level == 0:
        return node.module or ""
    package = path.relative_to(_SOURCE_ROOT).with_suffix("").parts[:-1]
    parent = package[: len(package) - node.level + 1]
    suffix = () if node.module is None else tuple(node.module.split("."))
    return ".".join((*parent, *suffix))


def _build_draft_call_sites() -> list[tuple[str, int, ast.Call]]:
    """Locate every AST call resolved to the canonical filing draft builder."""
    sites: list[tuple[str, int, ast.Call]] = []
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        builder_names: set[str] = set()
        builder_module_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and _resolved_import_module(path, node) == _BUILDER_MODULE:
                builder_names.update(alias.asname or alias.name for alias in node.names if alias.name == "build_draft")
            elif isinstance(node, ast.Import):
                builder_module_names.update(
                    alias.asname or alias.name for alias in node.names if alias.name == _BUILDER_MODULE
                )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            direct_call = isinstance(node.func, ast.Name) and node.func.id in builder_names
            module_call = (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "build_draft"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in builder_module_names
            )
            if direct_call or module_call:
                sites.append((path.relative_to(_SOURCE_ROOT).as_posix(), node.lineno, node))
    return sites


def test_scope_caller_scan_reaches_production_and_test_consumers() -> None:
    """The ratchet cannot pass vacuously if import resolution drifts."""
    callers = {relative for relative, _, _ in _build_draft_call_sites()}

    assert "cadrumo/application/filing/_import.py" in callers
    assert "cadrumo/application/modelo/_workflow_gate.py" in callers
    assert "cadrumo/application/filing/tests/test_filing.py" in callers


def test_every_build_draft_caller_declares_the_m303_scope_keyword() -> None:
    """Every caller decides the M303 branch rather than inheriting a hidden default."""
    omissions = [
        f"{relative}:{lineno}"
        for relative, lineno, call in _build_draft_call_sites()
        if not any(keyword.arg == _SCOPE_KEYWORD for keyword in call.keywords)
    ]

    assert omissions == [], (
        "Every cadrumo.application.filing.build_draft caller must pass "
        f"{_SCOPE_KEYWORD} explicitly; missing: {omissions}"
    )


def test_build_draft_signature_rejects_an_omitted_m303_scope_keyword() -> None:
    """The public callable itself has no default escape hatch for the scope decision."""
    with pytest.raises(TypeError, match=_SCOPE_KEYWORD):
        inspect.signature(build_draft).bind(
            modelo="130",
            period=object(),
            profile=object(),
            inputs={},
            schema_provider=object(),
        )
