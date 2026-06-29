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
import sys
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SRC_ROOT = SRC_AEAT


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _collect_function_defs(
    source_root: Path,
) -> dict[str, list[Path]]:
    """Return a mapping from function name to list of files that define it.

    Consumes the shared production AST inventory scoped to *source_root*.
    """
    defs: dict[str, list[Path]] = {}
    for py_file, tree in production_ast_items():
        if not py_file.is_relative_to(source_root):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(node.name, []).append(py_file)
    return defs


# ---------------------------------------------------------------------------
# Exactly one definition of canonical_decimal_string
# ---------------------------------------------------------------------------


def test_canonical_decimal_string_has_exactly_one_definition_site() -> None:
    """AST walk across src/aeat/ must find exactly one def site.

    Uses the shared per-file AST cache so the scan stays scoped to production
    modules.
    """
    all_defs = _collect_function_defs(_SRC_ROOT)
    sites = all_defs.get("canonical_decimal_string", [])
    relative_sites = [aeat_relative(p) for p in sites]
    assert len(sites) == 1, (
        f"Expected exactly 1 definition of canonical_decimal_string; found {len(sites)}: {relative_sites}"
    )
    canonical_home = sites[0]
    assert "domain" in canonical_home.parts and "_identifiers" in canonical_home.name, (
        f"canonical_decimal_string must be defined in domain/_identifiers.py; found at {canonical_home}"
    )


# ---------------------------------------------------------------------------
# _decimal.py is deleted; financial package no longer defines its own
# ---------------------------------------------------------------------------


def test_financial_decimal_module_is_deleted() -> None:
    """aeat.adapters.inbound.financial._decimal must not exist as a file."""
    decimal_module_path = _SRC_ROOT / "adapters" / "inbound" / "financial" / "_decimal.py"
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

    from ..adapters.inbound.financial import canonical_decimal
    from ..domain._identifiers import canonical_decimal_string

    assert canonical_decimal is canonical_decimal_string, (
        "aeat.adapters.inbound.financial.canonical_decimal must be the same "
        "object as aeat.domain._identifiers.canonical_decimal_string; "
        "check the __init__.py import alias."
    )
