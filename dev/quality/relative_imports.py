r"""Enforce relative self-imports inside the repository's Python packages.

Ruff's `flake8-tidy-imports.banned-api` (TID251) resolves relative
imports back to their absolute path before matching the banned prefix,
so banning `cadrumo` or `dev` would also flag every legitimate relative
self-import. This script exists to fill that gap for both package roots.

It walks the AST of every `*.py` file under `src/cadrumo/` and `dev/` and
reports absolute imports of the package that owns each file. AST
parsing (rather than regex) ensures absolute-import-looking text inside
docstrings or `textwrap.dedent` blocks does not produce false positives.

Intended invocation:

* `just check-relative-imports` â€” runs this with no arguments (full-tree scan).
* `prek run` â€” runs as a local hook with the staged file paths
  appended (per-file scan); see `prek.toml`.
* Direct invocation: `python -m dev.quality.relative_imports [PATH...]`.
  When PATHs are supplied, only those files are scanned (any path
  outside `src/cadrumo/` and `dev/` is silently skipped).

Inside ``src/cadrumo`` absolute ``cadrumo.*`` self-imports are forbidden.
Inside ``dev`` absolute ``dev.*`` self-imports are forbidden. Cross-package
``dev -> cadrumo`` imports remain absolute and are permitted.

Known blind-spot: dynamic-import strings such as
``pytest.importorskip("cadrumo.X")`` or ``importlib.import_module("cadrumo.X")``
are NOT flagged because the AST sees them as plain string constants.
This is intentional â€” string-form module names are sometimes the
right tool (placeholder gates, plugin loaders), and a heuristic match
on every "cadrumo."-prefixed string would produce noise. New contributors
adding dynamic-import sites should prefer relative-equivalent helpers
where possible; reviewers should grep for `"cadrumo\\."` in any new code.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8
SRC_CADRUMO = REPO_ROOT / "src" / "cadrumo"
DEV_ROOT = REPO_ROOT / "dev"
PACKAGE_ROOTS: tuple[tuple[Path, str], ...] = (
    (SRC_CADRUMO, "cadrumo"),
    (DEV_ROOT, "dev"),
)

# Sanity cap: any single Python source file larger than this is almost
# certainly not handwritten code (vendored blob, generated dump, mis-
# committed binary). Reject loudly rather than risk an OOM during
# pre-commit. The largest legitimate file under src/cadrumo/ is well under
# 200 kB; 2 MB gives generous headroom while still catching pathological
# inputs.
_MAX_SOURCE_BYTES = 2 * 1024 * 1024


def _scan_file(path: Path, package: str) -> tuple[list[tuple[int, str]], list[str]]:
    """Return findings and errors for absolute self-imports in ``path``.

    `findings` is a list of (lineno, rendered) tuples. `errors` is a
    list of human-readable diagnostic strings; non-empty when the file
    could not be processed (oversized, undecodable, syntactically
    invalid). Never silently swallows failures.
    """
    findings: list[tuple[int, str]] = []
    errors: list[str] = []

    try:
        size = path.stat().st_size
    except OSError as exc:
        errors.append(f"{path}: stat failed: {exc}")
        return findings, errors

    if size > _MAX_SOURCE_BYTES:
        errors.append(
            f"{path}: file is {size} bytes (limit {_MAX_SOURCE_BYTES}); "
            "refusing to scan. If this is a legitimate large source, raise "
            "_MAX_SOURCE_BYTES; otherwise inspect why a binary or blob "
            "landed in src/cadrumo/.",
        )
        return findings, errors

    try:
        source = path.read_text(encoding=_UTF_8)
    except UnicodeDecodeError as exc:
        errors.append(f"{path}: not valid UTF-8: {exc}")
        return findings, errors
    except OSError as exc:
        errors.append(f"{path}: read failed: {exc}")
        return findings, errors

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"{path}:{exc.lineno or 0}: SyntaxError: {exc.msg}")
        return findings, errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != package and not alias.name.startswith(f"{package}."):
                    continue
                rendered = f"import {alias.name}"
                if alias.asname:
                    rendered += f" as {alias.asname}"
                findings.append((node.lineno, rendered))
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module is None:
            continue
        if node.module != package and not node.module.startswith(f"{package}."):
            continue
        names = ", ".join(alias.name + (f" as {alias.asname}" if alias.asname else "") for alias in node.names)
        findings.append((node.lineno, f"from {node.module} import {names}"))
    return findings, errors


def _package_for_path(path: Path) -> str | None:
    """Return the owning package for a repository package source path."""
    resolved = path.resolve()
    for root, package in PACKAGE_ROOTS:
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return package
    return None


def _resolve_targets(args: list[str]) -> list[Path]:
    """Pick the files to scan.

    With no args, walk every Python file under both governed package roots.
    With args, keep only Python files inside either root.
    """
    if not args:
        return sorted(
            path
            for root, _package in PACKAGE_ROOTS
            for path in scan_directory(root, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
        )

    targets: list[Path] = []
    for raw in args:
        # Resolve relative to the current working directory â€” standard
        # CLI semantics. prek invokes hooks from the repo root, so this
        # also handles repo-root-relative paths correctly.
        candidate = Path(raw).resolve()
        if candidate.suffix != ".py":
            continue
        if _package_for_path(candidate) is None:
            continue
        if not candidate.is_file():
            continue
        targets.append(candidate)
    return targets


def main(argv: list[str] | None = None) -> int:
    """Scan the target files and report any absolute ``cadrumo`` imports.

    Args:
        argv: Optional explicit path list; defaults to ``sys.argv[1:]``.

    Returns:
        ``0`` when the tree is clean, ``1`` on findings or unscannable
        files, and ``2`` when ``src/cadrumo`` is not present.
    """
    args = list(argv) if argv is not None else sys.argv[1:]

    missing = [root for root, _package in PACKAGE_ROOTS if not root.is_dir()]
    if missing:
        sys.stderr.write("package root(s) not found: " + ", ".join(str(path) for path in missing) + "\n")
        return 2

    targets = _resolve_targets(args)

    all_findings: list[tuple[Path, int, str]] = []
    all_errors: list[str] = []
    for path in targets:
        package = _package_for_path(path)
        if package is None:
            continue
        findings, errors = _scan_file(path, package)
        for lineno, rendered in findings:
            all_findings.append((path, lineno, rendered))
        all_errors.extend(errors)

    if all_errors:
        sys.stderr.write(
            "dev/quality/relative_imports.py: refusing to certify the tree because "
            f"{len(all_errors)} file(s) could not be scanned:\n",
        )
        for err in all_errors:
            sys.stderr.write(f"  {err}\n")
        sys.stderr.write("\n")

    if all_findings:
        sys.stderr.write(
            "Absolute package self-imports are banned inside src/cadrumo/ and dev/.\n"
            "Use relative imports (`from .module import X` or `from ..sibling import Y`).\n\n",
        )
        for path, lineno, line in all_findings:
            rel = path.relative_to(REPO_ROOT)
            sys.stderr.write(f"{rel}:{lineno}: {line}\n")
        sys.stderr.write(f"\n{len(all_findings)} violation(s).\n")

    if all_errors or all_findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
