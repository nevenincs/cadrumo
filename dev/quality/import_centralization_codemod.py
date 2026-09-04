"""Codemod: rewrite cross-package private imports onto owning facades.

Rewrites production files by default, and can also (or exclusively) rewrite
test-only files. Consumes the same AST walk as ``dev/quality/import_hygiene_scan.py``
(re-run fresh, not from a stale JSON) and, for every ``ImportFrom`` statement
that reaches into a foreign package's private submodule where the imported
name is resolvable from the owning package's top-level facade, rewrites the
statement to import from the facade instead.

By default only production (non-test) files are visited.
Pass ``--include-tests`` to also visit test files (``tests/`` directories,
``test_*`` modules, and ``conftest``); combine with
``--tests-only`` to restrict the rewrite to test files exclusively once the
production sweep has already landed.

Behavior-preserving only:

* Mixed imports (some names facaded, some still private) are split into two
  ``from`` statements -- the still-private names keep the private import.
* ``if TYPE_CHECKING:`` blocks are rewritten in place at their existing
  indentation.
* Aliased imports (``import X as Y``) preserve the alias.
* Relative-vs-absolute import style is preserved per file (a file already
  using relative imports for its own package tree keeps using relative
  imports for the rewritten statement when the facade is reachable via a
  relative path of the same or lower depth; otherwise falls back to the
  absolute ``cadrumo....`` form, which is always valid).
* Intra-package imports are always left untouched -- the scanner's
  ``find_private_import_violations`` already excludes same-package
  importers.

Read-only unless ``--apply`` is passed. ``--only-file PATH`` restricts the
rewrite to one file (useful for verifying a single batch before committing).

    python -m dev.quality.import_centralization_codemod --apply
    python -m dev.quality.import_centralization_codemod --apply --only-file src/cadrumo/application/modelo/calculation_actions.py
    python -m dev.quality.import_centralization_codemod --apply --tests-only --only-file src/cadrumo/domain/modelos/tests/test_foo.py
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory

# Imported through the package rather than by inserting this directory on
# ``sys.path`` and importing the bare name. That loaded the sibling as a
# TOP-LEVEL module, so its own ``from .._paths import ...`` had no parent
# package and raised - which made this codemod unimportable by any route,
# including ``python -m``. A tool that rewrites source files behind an
# ``--apply`` flag had been dead for as long as nothing imported it.
from . import import_hygiene_scan as scan

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
PKG_ROOT = SRC_ROOT / "cadrumo"
_UTF_8: Final[str] = "utf-8"


@dataclass
class RewritePlan:
    """One ``ImportFrom`` statement to rewrite in one file."""

    path: Path
    node: ast.ImportFrom
    owning_package: str
    facaded_aliases: list[ast.alias]
    private_aliases: list[ast.alias]


def _module_is_package(path: Path) -> bool:
    return path.name == "__init__.py"


def _relative_prefix_for(importer_mod: str, importer_is_pkg: bool, target_mod: str) -> str | None:
    """Return a relative ``from`` clause (e.g. ``...core``) reaching *target_mod*.

    Returns ``None`` when the target cannot be expressed relatively (should not
    happen for any ``cadrumo.*`` target, but guards against edge cases at the
    package root).
    """
    importer_parts = importer_mod.split(".")
    base_parts = importer_parts if importer_is_pkg else importer_parts[:-1]
    target_parts = target_mod.split(".")

    # Find the common ancestor length.
    common = 0
    while common < len(base_parts) and common < len(target_parts) and base_parts[common] == target_parts[common]:
        common += 1

    # levels above base_parts needed to reach the common ancestor.
    up = len(base_parts) - common
    remainder = target_parts[common:]
    dots = "." * (up + 1)
    if not remainder:
        return dots
    return dots + ".".join(remainder)


def _existing_import_style(tree: ast.Module) -> str:
    """Return 'relative' or 'absolute' -- whichever this file's cadrumo.* imports mostly use."""
    relative = 0
    absolute = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                relative += 1
            elif node.module and node.module.startswith("cadrumo"):
                absolute += 1
    return "relative" if relative >= absolute else "absolute"


def _format_import_stmt(
    *,
    indent: str,
    module_clause: str,
    aliases: list[ast.alias],
) -> str:
    names_sorted = sorted(aliases, key=lambda a: a.asname or a.name)
    rendered = [f"{a.name} as {a.asname}" if a.asname else a.name for a in names_sorted]
    if len(rendered) == 1:
        single = f"{indent}from {module_clause} import {rendered[0]}\n"
        if len(single.rstrip("\n")) <= 119:
            return single
    joined = ",\n".join(f"{indent}    {r}" for r in rendered)
    return f"{indent}from {module_clause} import (\n{joined},\n{indent})\n"


def collect_plans(
    *, only_file: Path | None, include_tests: bool = False, tests_only: bool = False
) -> tuple[list[RewritePlan], dict[str, scan.FacadeInfo]]:
    """Collect every rewritable ``ImportFrom`` statement under ``src/cadrumo``.

    ``include_tests=False`` (the default) preserves production-only
    behavior. ``include_tests=True`` also visits test
    modules; ``tests_only=True`` additionally excludes production modules,
    restricting the sweep to test files only.
    """
    facades = scan.discover_facades()

    py_files = list(scan_directory(PKG_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",)))
    if only_file is not None:
        py_files = [p for p in py_files if p == only_file]

    plans: list[RewritePlan] = []
    for path in py_files:
        mod = scan.module_name_for(path)
        is_test = scan.is_test_module(mod, path)
        if is_test and not include_tests:
            continue
        if not is_test and tests_only:
            continue
        is_pkg = _module_is_package(path)
        try:
            src = path.read_text(encoding=_UTF_8)
            tree = ast.parse(src, filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = scan.resolve_relative_import(mod, is_pkg, node.level, node.module)
            if target is None or not target.startswith("cadrumo"):
                continue
            if not scan.has_private_component(target):
                continue
            owner = scan.owning_package(target)
            if mod == owner or mod.startswith(owner + "."):
                continue
            facade_info = facades.get(owner)
            if facade_info is None or not facade_info.has_real_all:
                continue

            facaded_aliases: list[ast.alias] = []
            private_aliases: list[ast.alias] = []
            skip = False
            for alias in node.names:
                if alias.name == "*":
                    skip = True
                    break
                if alias.name in facade_info.all_names:
                    facaded_aliases.append(alias)
                else:
                    private_aliases.append(alias)
            if skip or not facaded_aliases:
                continue

            plans.append(
                RewritePlan(
                    path=path,
                    node=node,
                    owning_package=owner,
                    facaded_aliases=facaded_aliases,
                    private_aliases=private_aliases,
                )
            )
    return plans, facades


def apply_plans_to_file(path: Path, plans: list[RewritePlan]) -> bool:
    """Rewrite every planned ``ImportFrom`` statement in *path*. Returns True if changed."""
    src = path.read_text(encoding=_UTF_8)
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src, filename=str(path))
    mod = scan.module_name_for(path)
    is_pkg = _module_is_package(path)
    style = _existing_import_style(tree)

    # Sort by start line descending so earlier edits don't shift later line numbers.
    plans_sorted = sorted(plans, key=lambda p: p.node.lineno, reverse=True)

    changed = False
    for plan in plans_sorted:
        node = plan.node
        start = node.lineno - 1
        end = (node.end_lineno or node.lineno) - 1
        indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]

        if style == "relative":
            rel = _relative_prefix_for(mod, is_pkg, plan.owning_package)
            module_clause = rel if rel is not None else plan.owning_package
        else:
            module_clause = plan.owning_package

        new_stmts = []
        if plan.private_aliases:
            # Keep the still-private names on their original private import,
            # preserving the original module clause exactly (relative level +
            # module string) and only the facaded subset moves.
            priv_clause = "." * node.level + (node.module or "") if node.level and node.level > 0 else node.module or ""
            new_stmts.append(
                _format_import_stmt(indent=indent, module_clause=priv_clause, aliases=plan.private_aliases)
            )
        new_stmts.append(_format_import_stmt(indent=indent, module_clause=module_clause, aliases=plan.facaded_aliases))

        replacement = "".join(new_stmts)
        lines[start : end + 1] = [replacement]
        changed = True

    if changed:
        path.write_text("".join(lines), encoding=_UTF_8, newline="\n")
    return changed


def main() -> int:
    """Run the codemod: dry-run report by default, or apply with ``--apply``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run report only)")
    parser.add_argument("--only-file", type=Path, default=None, help="Restrict to one file (repo-relative or absolute)")
    parser.add_argument("--include-tests", action="store_true", help="Also visit test files (default: production only)")
    parser.add_argument(
        "--tests-only", action="store_true", help="Restrict the sweep to test files only (implies --include-tests)"
    )
    args = parser.parse_args()

    only_file = None
    if args.only_file is not None:
        only_file = args.only_file if args.only_file.is_absolute() else (REPO_ROOT / args.only_file)
        only_file = only_file.resolve()

    include_tests = args.include_tests or args.tests_only
    plans, _facades = collect_plans(only_file=only_file, include_tests=include_tests, tests_only=args.tests_only)

    by_file: dict[Path, list[RewritePlan]] = defaultdict(list)
    for plan in plans:
        by_file[plan.path].append(plan)

    print(f"Collected {len(plans)} rewritable ImportFrom statement(s) across {len(by_file)} file(s).")
    for path in sorted(by_file):
        n_names = sum(len(p.facaded_aliases) for p in by_file[path])
        print(f"  {path.relative_to(REPO_ROOT)} :: {len(by_file[path])} stmt(s), {n_names} name(s)")

    if not args.apply:
        print("\nDry run only (pass --apply to write changes).")
        return 0

    n_changed = 0
    for path, file_plans in by_file.items():
        if apply_plans_to_file(path, file_plans):
            n_changed += 1
    print(f"\nRewrote {n_changed} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
