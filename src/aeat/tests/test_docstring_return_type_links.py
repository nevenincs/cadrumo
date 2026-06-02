"""Navigability gate: a documented public function links its aeat return type.

The spine gate (`test_docstring_core_struct_links.py`) keeps the canonical core
structs reachable. This gate extends navigability to the wider collaborator
graph along its highest-signal edge: the return type. A reader asking "what does
this produce, and where is that type defined?" should find a cross-reference in
the function's own docstring rather than a bare type name they must grep for.

The rule is objective. For every public function or method that already has a
docstring, if its return annotation names an aeat-defined public class that has
a single canonical definition (so it is documentable and a bare ``:class:`Name```
resolves), that class must be cross-referenced somewhere in the function's
docstring. Functions without a docstring are out of scope here; docstring
presence is enforced by the ruff/interrogate gates.

The gate is hard-cut with no stored baseline: it recomputes the violation
worklist from the AST on every run and fails with a precise
``module::function -> :class:`ReturnType``` enumeration, so coverage can only
ratchet to green. It carries the ``docs`` marker and runs in the documentation
CI lane.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core, pytest.mark.docs]

_SRC_ROOT = Path(__file__).resolve().parents[2]
_PKG_ROOT = _SRC_ROOT / "aeat"

_ROLE = re.compile(r":(?:class|obj|meth|func|data|attr|exc):`[^`]*?([A-Za-z_][A-Za-z0-9_]*)`")


def _is_in_scope(path: Path) -> bool:
    posix = path.as_posix()
    return not (path.name.startswith("test_") or path.name == "conftest.py" or "/tests/" in posix or "/_data/" in posix)


def _module_name(path: Path) -> str:
    rel = path.relative_to(_SRC_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _annotation_names(node: ast.AST) -> set[str]:
    """Return every bare identifier appearing in a (possibly nested) annotation."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _linkable_classes() -> set[str]:
    """Public aeat classes with exactly one canonical definition (documentable)."""
    counts: dict[str, int] = defaultdict(int)
    for path in _PKG_ROOT.rglob("*.py"):
        if not _is_in_scope(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                counts[node.name] += 1
    return {name for name, n in counts.items() if n == 1}


def test_public_functions_link_their_aeat_return_type() -> None:
    """A documented public function must cross-link an aeat-typed return annotation."""
    linkable = _linkable_classes()
    violations: dict[str, list[str]] = defaultdict(list)
    for path in _PKG_ROOT.rglob("*.py"):
        if not _is_in_scope(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        module = _module_name(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name.startswith("_") or node.returns is None:
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            linked = {m for m in _ROLE.findall(doc)}
            returned = {n for n in _annotation_names(node.returns) if n in linkable}
            for name in sorted(returned - linked):
                violations[f"{module}::{node.name}"].append(name)

    if violations:
        total = sum(len(v) for v in violations.values())
        lines = [
            f"{total} public functions return an aeat type their docstring does not link.",
            "Cross-link the return type (e.g. in the Returns: section) with :class:`Name`:",
            "",
        ]
        for symbol in sorted(violations):
            for name in sorted(violations[symbol]):
                lines.append(f"  {symbol}  ->  :class:`{name}`")
        pytest.fail("\n".join(lines))
