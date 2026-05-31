"""Real-behavior verification for W07.P33 cleanup steps.

S528 — Confirms aeat.core._time has been fully deleted with no import survivors.
S530 — Re-runs the W2 cast-rationale inventory contract to confirm every
       production cast() call carries an inline CAST-RATIONALE-* marker.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
from typing import Iterator

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent
_RATIONALE_MARKER = "CAST-RATIONALE-"


# ---------------------------------------------------------------------------
# S528 — Deletion verification
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
            f"{len(violations)} source file(s) still reference aeat.core._time:\n  "
            + "\n  ".join(violations)
        )


# ---------------------------------------------------------------------------
# S530 — Cast-rationale inventory contract (mirrors test_cast_rationale_inventory)
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
        if isinstance(func, ast.Name) and func.id == "cast":
            yield node.lineno
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "cast"
            and isinstance(func.value, ast.Name)
            and func.value.id in ("typing", "t")
        ):
            yield node.lineno


def _collect_cast_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if path.name.startswith("test_"):
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


def test_every_production_cast_has_rationale_marker() -> None:
    """Every production cast() call must carry a CAST-RATIONALE-* marker (W2 contract re-run)."""
    violations = _collect_cast_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} cast() call(s) lack a CAST-RATIONALE-* marker:\n  {joined}\n\n"
            "Add a '# CAST-RATIONALE-<SLUG>: ...' comment on the cast line or "
            "in the immediately preceding comment block."
        )
