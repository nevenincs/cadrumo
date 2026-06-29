"""aeat.core._time deletion inventory and cast() rationale-marker invariant.

Confirms:
- aeat.core._time has been fully deleted with no import survivors.
- Every production cast() call carries an inline CAST-RATIONALE-* marker.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import cast_rationale_violations, production_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# aeat.core._time deletion verification
# ---------------------------------------------------------------------------


def test_aeat_core_time_module_deleted() -> None:
    """aeat.core._time must not be importable — the module has been deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aeat.core._time")


def test_no_source_imports_aeat_core_time() -> None:
    """No production source file may import from aeat.core._time."""
    violations: list[str] = []
    for path in production_python_files():
        source = path.read_text(encoding="utf-8", errors="replace")
        if "aeat.core._time" in source:
            violations.append(repo_relative(path))
    if violations:
        raise AssertionError(
            f"{len(violations)} source file(s) still reference aeat.core._time:\n  " + "\n  ".join(violations),
        )


# ---------------------------------------------------------------------------
# Cast-rationale inventory contract (mirrors test_cast_rationale_inventory)
# ---------------------------------------------------------------------------


def _collect_cast_violations(source_tree_ast: Mapping[Path, ast.AST] | None = None) -> list[str]:
    """Return the list of ``cast()`` sites that lack a rationale marker.

    When *source_tree_ast* is supplied (test path), consume the cached
    parsed AST per file and read the raw source text only to render line
    snippets. When omitted, fall back to walk-and-parse so the helper's
    signature stays compatible with importlib callers.
    """
    return cast_rationale_violations(source_tree_ast)


def test_every_production_cast_has_rationale_marker() -> None:
    """Every production cast() call must carry a CAST-RATIONALE-* marker.

    Consumes the shared production AST cache so the per-file parse cost
    is amortised across the full ratchet suite.
    """
    violations = _collect_cast_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} cast() call(s) lack a CAST-RATIONALE-* marker:\n  {joined}\n\n"
            "Add a '# CAST-RATIONALE-<SLUG>: ...' comment on the cast line or "
            "in the immediately preceding comment block.",
        )
