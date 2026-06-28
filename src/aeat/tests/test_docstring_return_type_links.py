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

The gate uses an explicit backlog baseline: it recomputes the violation
worklist from the AST on every run and fails when new items appear or when fixed
items remain in the baseline. Coverage can only ratchet toward an empty set.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import ast_for_path, module_name, production_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROLE = re.compile(r":(?:class|obj|meth|func|data|attr|exc):`[^`]*?([A-Za-z_][A-Za-z0-9_]*)`")

_RETURN_TYPE_LINK_BASELINE: frozenset[tuple[str, str]] = frozenset()


def _annotation_names(node: ast.AST) -> set[str]:
    """Return every bare identifier appearing in a (possibly nested) annotation."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _linkable_classes(source_tree_ast: Mapping[Path, ast.AST]) -> set[str]:
    """Public aeat classes with exactly one canonical definition (documentable)."""
    counts: dict[str, int] = defaultdict(int)
    for path in production_python_files():
        tree = ast_for_path(path, source_tree_ast)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                counts[node.name] += 1
    return {name for name, n in counts.items() if n == 1}


def test_public_functions_link_their_aeat_return_type(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """A documented public function must cross-link an aeat-typed return annotation."""
    linkable = _linkable_classes(source_tree_ast)
    violations: set[tuple[str, str]] = set()
    for path in production_python_files():
        tree = ast_for_path(path, source_tree_ast)
        if tree is None:
            continue
        module = module_name(path)
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
                violations.add((f"{module}::{node.name}", name))

    new_violations = sorted(violations - _RETURN_TYPE_LINK_BASELINE)
    resolved_baseline = sorted(_RETURN_TYPE_LINK_BASELINE - violations)
    if new_violations or resolved_baseline:
        lines = [
            f"{len(new_violations)} new public return-type docstring link violation(s).",
            "Cross-link the return type (e.g. in the Returns: section) with :class:`Name`:",
            "",
        ]
        for symbol, name in new_violations:
            lines.append(f"  + {symbol}  ->  :class:`{name}`")
        if resolved_baseline:
            lines.extend(("", "Resolved baseline entries; remove them from _RETURN_TYPE_LINK_BASELINE:"))
            for symbol, name in resolved_baseline:
                lines.append(f"  - {symbol}  ->  :class:`{name}`")
        pytest.fail("\n".join(lines))
