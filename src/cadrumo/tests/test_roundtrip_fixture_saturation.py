"""Structural gate: roundtrip-fixture builders must saturate defaultable fields.

Every defaultable field must be populated with a non-default value in a
roundtrip fixture. A save-drops-field / load-re-defaults regression is invisible
when the fixture uses the default.

The gate enumerates the dedicated roundtrip test files (``test_*roundtrip*.py``
and ``test_*anti_tautology*.py``) live from the tree, and requires every
``_populated_*`` function (the project's canonical naming convention for "all
optional fields set") to satisfy at least one of the following structural
markers:

a. The enclosing file's module docstring mentions "populate" or "non-default"
   or "optional" — indicating the author was aware of the rule.
b. The function's own docstring mentions "populate", "non-default", "optional",
   or "saturation".
c. The function body contains at least 4 keyword-argument assignments in its
   return call(s) — a heuristic proxy for "not just required fields".

A function failing all three markers is reported as an unsaturated candidate.

There is no waiver list. The one that existed was keyed by
``path:lineno:function_name``, and a key that bakes in a line number cannot be
made durable -- it rots on the next edit to the file above it, and it rotted:
its path also predated the move of tests into ``tests/`` packages, so it had
matched nothing for a long time while still reading as live coverage. A builder
that genuinely cannot saturate should say so in its own docstring, which
satisfies marker (b) at the site and cannot drift away from the function it
describes.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TESTS_DIR = Path(__file__).parent
_AEAT_ROOT = _TESTS_DIR.parent

# Saturation keywords searched in docstrings and file module docstrings.
_SATURATION_KEYWORDS = frozenset({"populate", "non-default", "optional", "saturation", "defaultable"})


def _file_module_docstring(tree: ast.Module) -> str:
    """Return the module-level docstring, lowercased, or empty string."""
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        return tree.body[0].value.value.lower()
    return ""


def _function_docstring(func: ast.FunctionDef) -> str:
    """Return the function's docstring, lowercased, or empty string."""
    if (
        func.body
        and isinstance(func.body[0], ast.Expr)
        and isinstance(func.body[0].value, ast.Constant)
        and isinstance(func.body[0].value.value, str)
    ):
        return func.body[0].value.value.lower()
    return ""


def _max_kwargs_in_return_calls(func: ast.FunctionDef) -> int:
    """Return the maximum keyword-argument count across all Call nodes in return stmts."""
    max_kwargs = 0
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            for call in ast.walk(node.value):
                if isinstance(call, ast.Call):
                    max_kwargs = max(max_kwargs, len(call.keywords))
    return max_kwargs


def _collect_populated_builders(
    src_root: Path,
) -> list[tuple[str, int, str, ast.FunctionDef, ast.Module]]:
    """Collect (rel_posix_path, lineno, name, func_node, module_tree) for all _populated_* builders."""
    patterns = ["test_*roundtrip*.py", "test_*anti_tautology*.py"]
    files: set[Path] = set()
    for pat in patterns:
        files.update(scan_directory(src_root, pattern=pat, recursive=True))

    results = []
    for rf in sorted(files):
        try:
            source = rf.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(rf))
        except (OSError, SyntaxError):
            continue
        rel = rf.relative_to(src_root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_populated_"):
                results.append((rel, node.lineno, node.name, node, tree))
    return results


def test_populated_builders_carry_saturation_markers() -> None:
    """Every ``_populated_*`` builder must document or demonstrate field saturation.

    Three structural markers are accepted (see module docstring for rationale):
    a. File module docstring contains a saturation keyword.
    b. Function docstring contains a saturation keyword.
    c. At least 4 keyword arguments appear in a return-call expression.

    There is no waiver channel: a builder that cannot saturate documents that
    in its own docstring, which is marker (b).
    """
    builders = _collect_populated_builders(_AEAT_ROOT)

    assert builders, (
        "No _populated_* builders found in roundtrip test files — "
        "either the naming convention changed or the file pattern is wrong."
    )

    failures: list[str] = []
    for rel, lineno, name, func_node, module_tree in builders:
        module_doc = _file_module_docstring(module_tree)
        func_doc = _function_docstring(func_node)
        max_kwargs = _max_kwargs_in_return_calls(func_node)

        has_module_keyword = any(kw in module_doc for kw in _SATURATION_KEYWORDS)
        has_func_keyword = any(kw in func_doc for kw in _SATURATION_KEYWORDS)
        has_sufficient_kwargs = max_kwargs >= 4

        if not (has_module_keyword or has_func_keyword or has_sufficient_kwargs):
            failures.append(
                f"  {rel}:{lineno} {name!r} — "
                f"no saturation marker (module_kw={has_module_keyword}, "
                f"func_kw={has_func_keyword}, max_kwargs={max_kwargs})",
            )

    if failures:
        joined = "\n".join(failures)
        raise AssertionError(
            f"Found {len(failures)} _populated_* builder(s) lacking saturation evidence:\n{joined}\n\n"
            "Fix by:\n"
            "  1. Adding a docstring/comment explaining that all optional fields are set, OR\n"
            "  2. Populating more fields (>=4 keyword args in return call).",
        )
