"""aeat.core._time deletion inventory and cast() rationale-marker invariant.

Confirms:
- aeat.core._time has been fully deleted with no import survivors.
- Every production cast() call carries an inline CAST-RATIONALE-* marker.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
from collections.abc import Iterator, Mapping

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = pathlib.Path(__file__).parent.parent
_RATIONALE_MARKER = "CAST-RATIONALE-"


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
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if "aeat.core._time" in source:
            rel = path.relative_to(_SRC_ROOT.parent.parent)
            violations.append(str(rel))
    if violations:
        raise AssertionError(
            f"{len(violations)} source file(s) still reference aeat.core._time:\n  " + "\n  ".join(violations),
        )


# ---------------------------------------------------------------------------
# Cast-rationale inventory contract (mirrors test_cast_rationale_inventory)
# ---------------------------------------------------------------------------


def _is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def _has_rationale_above(lines: list[str], cast_lineno: int) -> bool:
    idx = cast_lineno - 1
    line = lines[idx]
    if _RATIONALE_MARKER in line:
        return True
    scan = idx - 1
    while scan >= 0:
        candidate = lines[scan]
        if _RATIONALE_MARKER in candidate:
            return True
        if _is_comment_or_blank(candidate):
            scan -= 1
        else:
            break
    return False


def _cast_call_linenos(tree: ast.AST) -> Iterator[int]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "cast") or (
            isinstance(func, ast.Attribute)
            and func.attr == "cast"
            and isinstance(func.value, ast.Name)
            and func.value.id in ("typing", "t")
        ):
            yield node.lineno


def _collect_cast_violations(
    source_tree_ast: Mapping[pathlib.Path, ast.AST] | None = None,
) -> list[str]:
    """Return the list of ``cast()`` sites that lack a rationale marker.

    When *source_tree_ast* is supplied (test path), consume the cached
    parsed AST per file and read the raw source text only to render line
    snippets. When omitted, fall back to walk-and-parse so the helper's
    signature stays compatible with importlib callers.
    """
    violations: list[str] = []
    if source_tree_ast is None:
        for path in sorted(_SRC_ROOT.rglob("*.py")):
            if path.name.startswith("test_") or "tests" in path.parts:
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError:
                continue
            lines = source.splitlines()
            for lineno in _cast_call_linenos(tree):
                if not _has_rationale_above(lines, lineno):
                    rel = path.relative_to(_SRC_ROOT.parent.parent)
                    violations.append(f"{rel}:{lineno}")
        return violations

    for path in sorted(source_tree_ast):
        if path.name.startswith("test_") or "tests" in path.parts:
            continue
        try:
            path.relative_to(_SRC_ROOT)
        except ValueError:
            continue
        tree = source_tree_ast[path]
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno in _cast_call_linenos(tree):
            if not _has_rationale_above(lines, lineno):
                rel = path.relative_to(_SRC_ROOT.parent.parent)
                violations.append(f"{rel}:{lineno}")
    return violations


def test_every_production_cast_has_rationale_marker(
    source_tree_ast: Mapping[pathlib.Path, ast.AST],
) -> None:
    """Every production cast() call must carry a CAST-RATIONALE-* marker.

    Consumes the session-scoped AST cache so the per-file parse cost is
    amortised across the full ratchet suite.
    """
    violations = _collect_cast_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} cast() call(s) lack a CAST-RATIONALE-* marker:\n  {joined}\n\n"
            "Add a '# CAST-RATIONALE-<SLUG>: ...' comment on the cast line or "
            "in the immediately preceding comment block.",
        )
