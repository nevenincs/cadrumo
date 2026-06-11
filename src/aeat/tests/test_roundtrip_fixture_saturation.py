"""Structural gate: roundtrip-fixture builders must saturate defaultable fields.

Per :mod:`aeat-roundtrip-discipline`: "Populate every defaultable field with a
non-default value in roundtrip fixtures." A save-drops-field / load-re-defaults
regression is invisible when the fixture uses the default.

This test applies two complementary checks across dedicated roundtrip test files
(``test_*roundtrip*.py`` and ``test_*anti_tautology*.py``):

1. **Snapshot integrity**: the builder-function inventory committed to
   ``src/aeat/_data/audit/s223-roundtrip-fixture-builders-2026-05-28.txt``
   is consistent with the current file tree — every listed file still exists.
   This catches renames or deletions that silently invalidate the audit.

2. **Saturation marker**: every ``_populated_*`` function (the project's
   canonical naming convention for "all optional fields set") must satisfy at
   least one of the following structural markers:

   a. The enclosing file's module docstring mentions "populate" or "non-default"
      or "optional" — indicating the author was aware of the rule.
   b. The function's own docstring mentions "populate", "non-default",
      "optional", or "saturation".
   c. The function body contains at least 4 keyword-argument assignments in its
      return call(s) — a heuristic proxy for "not just required fields".

   A function failing all three markers is reported as an unsaturated candidate.

Waivers are declared inline below in ``_WAIVERS`` and must justify why the
saturation rule does not apply (e.g. the model has no optional fields).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TESTS_DIR = Path(__file__).parent
_AEAT_ROOT = _TESTS_DIR.parent
_REPO_ROOT = _AEAT_ROOT.parent.parent

# Waivers: builder functions exempt from the saturation marker check.
# Format: "path:lineno:function_name" -> "rationale"
# Paths are relative to the repository src/aeat root (POSIX separators).
_WAIVERS: dict[str, str] = {
    # _populated_snapshot in test_borrador_100_roundtrip.py is waived
    # pending verification of snapshot-model optional-field coverage.
    "application/live/test_borrador_100_roundtrip.py:36:_populated_snapshot": (
        "snapshot model optional-field coverage unconfirmed"
    ),
}

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
        files.update(src_root.rglob(pat))

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


def test_snapshot_files_still_exist() -> None:
    """Every file listed in the behavior contract audit snapshot must still exist on disk.

    If a roundtrip test file is renamed or deleted the snapshot becomes stale.
    This test surfaces that drift before the next saturation audit runs blind.
    """
    snapshot_path = _AEAT_ROOT / "_data" / "audit" / "s223-roundtrip-fixture-builders-2026-05-28.txt"
    assert snapshot_path.exists(), f"S223 audit snapshot not found: {snapshot_path}"

    missing: list[str] = []
    for raw_line in snapshot_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Format: "src/aeat/path/to/file.py:lineno func_name NOTE"
        parts = line.split()
        if not parts:
            continue
        path_lineno = parts[0]
        # path_lineno is like "src/aeat/adapters/.../file.py:42"
        colon_idx = path_lineno.rfind(":")
        if colon_idx == -1:
            continue
        rel_path = path_lineno[:colon_idx]
        # rel_path starts with "src/aeat/"; strip to get relative-to-repo
        abs_path = _REPO_ROOT / Path(rel_path)
        if not abs_path.exists():
            missing.append(rel_path)

    if missing:
        joined = "\n  ".join(missing)
        raise AssertionError(
            f"S223 audit snapshot references {len(missing)} file(s) that no longer exist:\n  {joined}\n"
            "Update the snapshot in src/aeat/_data/audit/s223-roundtrip-fixture-builders-2026-05-28.txt.",
        )


def test_populated_builders_carry_saturation_markers() -> None:
    """Every ``_populated_*`` builder must document or demonstrate field saturation.

    Three structural markers are accepted (see module docstring for rationale):
    a. File module docstring contains a saturation keyword.
    b. Function docstring contains a saturation keyword.
    c. At least 4 keyword arguments appear in a return-call expression.

    Builders in ``_WAIVERS`` are exempt with a documented rationale.
    """
    builders = _collect_populated_builders(_AEAT_ROOT)

    assert builders, (
        "No _populated_* builders found in roundtrip test files — "
        "either the naming convention changed or the file pattern is wrong."
    )

    failures: list[str] = []
    for rel, lineno, name, func_node, module_tree in builders:
        waiver_key = f"{rel}:{lineno}:{name}"
        if waiver_key in _WAIVERS:
            continue

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
            "  2. Populating more fields (>=4 keyword args in return call), OR\n"
            "  3. Adding a waiver entry in test_roundtrip_fixture_saturation._WAIVERS with rationale.",
        )
