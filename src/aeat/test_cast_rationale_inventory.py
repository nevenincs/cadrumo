"""Inventory test: every production cast() call must carry a CAST-RATIONALE-* marker.

Rule
----
For every ``cast(`` occurrence in a non-test production module under
``src/aeat/``, either:

- the same line contains ``CAST-RATIONALE-``, OR
- scanning upward through immediately adjacent comment / blank lines reaches
  a line containing ``CAST-RATIONALE-`` before hitting any code line.

Rationale
---------
Unguarded ``cast()`` calls erase type-system information without leaving an
explanation for future readers.  The marker scheme enforces a concise,
grep-able audit trail at every escape hatch.

Exclusions
----------
- ``test_*.py`` files: test suites may reference cast() in assertions without
  a production rationale marker.
- Lines where ``cast(`` appears only inside a Python *string literal*
  (docstrings, rst-style prose) are excluded because they are not actual
  cast calls.  The heuristic: strip the line; if the only ``cast(`` is
  preceded by a quote character or occurs inside a triple-quoted block, skip.
  Rather than attempting full parse, we use a conservative AST walk per file
  to locate real ``cast()`` call nodes and their line numbers.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Iterator

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


_SRC_ROOT = pathlib.Path(__file__).parent
_RATIONALE_MARKER = "CAST-RATIONALE-"


def _is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def _has_rationale_above(lines: list[str], cast_lineno: int) -> bool:
    """Return True if a CAST-RATIONALE- marker appears on the cast line or in
    immediately preceding comment/blank lines (no intervening code)."""
    # cast_lineno is 1-based (from AST); convert to 0-based index.
    idx = cast_lineno - 1
    line = lines[idx]
    if _RATIONALE_MARKER in line:
        return True
    # Walk upward through comment/blank lines only.
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
    """Yield line numbers of genuine cast() / typing.cast() call expressions."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # bare cast(...)
        if isinstance(func, ast.Name) and func.id == "cast":
            yield node.lineno
        # typing.cast(...)
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "cast"
            and isinstance(func.value, ast.Name)
            and func.value.id in ("typing", "t")
        ):
            yield node.lineno


def _collect_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            # Unparseable file — skip; a separate lint gate catches this.
            continue
        lines = source.splitlines()
        for lineno in _cast_call_linenos(tree):
            if not _has_rationale_above(lines, lineno):
                rel = path.relative_to(_SRC_ROOT.parent.parent)
                violations.append(f"{rel}:{lineno}")
    return violations


def test_every_cast_has_rationale_marker() -> None:
    """Every production cast() call must have a CAST-RATIONALE-* comment."""
    violations = _collect_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} cast() call(s) lack a CAST-RATIONALE-* marker:\n  {joined}\n\n"
            "Add a '# CAST-RATIONALE-<SLUG>: ...' comment on the cast line or "
            "in the immediately preceding comment block."
        )
