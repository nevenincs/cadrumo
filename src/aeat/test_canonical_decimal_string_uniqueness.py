"""canonical_decimal_string uniqueness invariant.

Asserts:
1. ``canonical_decimal_string`` has exactly one definition site across
   ``src/aeat/`` (verified by AST walk of all Python source files).
2. The old duplicate name ``canonical_decimal`` in
   ``aeat.adapters.inbound.financial._decimal`` no longer exists as a
   module (the file is deleted); any surviving ``canonical_decimal`` name
   in the financial package re-exports from ``aeat.domain._identifiers``.
"""

from __future__ import annotations

import ast
import pathlib
import sys
from collections.abc import Mapping

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_SRC_ROOT = pathlib.Path(__file__).parent


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _collect_function_defs(
    source_root: pathlib.Path,
    source_tree_ast: Mapping[pathlib.Path, ast.AST] | None = None,
) -> dict[str, list[pathlib.Path]]:
    """Return a mapping from function name to list of files that define it.

    When *source_tree_ast* is supplied (test path), consume the cached
    parsed AST per file scoped to *source_root*. When omitted, fall back
    to walk-and-parse so the helper's signature stays compatible with
    importlib callers.
    """
    defs: dict[str, list[pathlib.Path]] = {}
    if source_tree_ast is None:
        for py_file in source_root.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.setdefault(node.name, []).append(py_file)
        return defs

    for py_file, tree in source_tree_ast.items():
        try:
            py_file.relative_to(source_root)
        except ValueError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(node.name, []).append(py_file)
    return defs


# ---------------------------------------------------------------------------
# Exactly one definition of canonical_decimal_string
# ---------------------------------------------------------------------------


def test_canonical_decimal_string_has_exactly_one_definition_site(
    source_tree_ast: Mapping[pathlib.Path, ast.AST],
) -> None:
    """AST walk across src/aeat/ must find exactly one def site.

    Consumes the session-scoped AST cache so the per-file parse cost is
    amortised across the full ratchet suite.
    """
    all_defs = _collect_function_defs(_SRC_ROOT, source_tree_ast)
    sites = all_defs.get("canonical_decimal_string", [])
    relative_sites = [p.relative_to(_SRC_ROOT) for p in sites]
    assert len(sites) == 1, (
        f"Expected exactly 1 definition of canonical_decimal_string; "
        f"found {len(sites)}: {relative_sites}"
    )
    canonical_home = sites[0]
    assert "domain" in canonical_home.parts and "_identifiers" in canonical_home.name, (
        f"canonical_decimal_string must be defined in domain/_identifiers.py; "
        f"found at {canonical_home}"
    )


# ---------------------------------------------------------------------------
# _decimal.py is deleted; financial package no longer defines its own
# ---------------------------------------------------------------------------


def test_financial_decimal_module_is_deleted() -> None:
    """aeat.adapters.inbound.financial._decimal must not exist as a file."""
    decimal_module_path = (
        _SRC_ROOT
        / "adapters"
        / "inbound"
        / "financial"
        / "_decimal.py"
    )
    assert not decimal_module_path.exists(), (
        f"Duplicate _decimal.py still present at {decimal_module_path}; "
        "delete the file and migrate callers to aeat.domain._identifiers."
    )


def test_financial_package_canonical_decimal_delegates_to_domain() -> None:
    """The name canonical_decimal re-exported by the financial package must
    be the same object as canonical_decimal_string from aeat.domain._identifiers.
    """
    # Ensure a clean import — drop any cached stale module
    for key in list(sys.modules.keys()):
        if "aeat.adapters.inbound.financial" in key or "aeat.domain._identifiers" in key:
            del sys.modules[key]

    from .adapters.inbound.financial import canonical_decimal  # type: ignore[attr-defined]
    from .domain._identifiers import canonical_decimal_string

    assert canonical_decimal is canonical_decimal_string, (
        "aeat.adapters.inbound.financial.canonical_decimal must be the same "
        "object as aeat.domain._identifiers.canonical_decimal_string; "
        "check the __init__.py import alias."
    )
