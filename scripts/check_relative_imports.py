"""Enforce the relative-imports mandate inside `src/aeat/` (#162).

Ruff's `flake8-tidy-imports.banned-api` (TID251) resolves relative
imports back to their absolute path before matching the banned prefix,
so banning `aeat` would also flag every legitimate `from .module import
X` inside `src/aeat/`. This script exists to fill that gap.

It walks the AST of every `*.py` file under `src/aeat/` and reports
any `import aeat[.X]` or `from aeat[.X] import Y` statement. AST
parsing (rather than regex) ensures absolute-import-looking text inside
docstrings or `textwrap.dedent` blocks does not produce false positives.

Intended invocation:

* `just lint` — runs this with no arguments (full-tree scan).
* `prek run` — runs as a local hook with the staged file paths
  appended (per-file scan); see `prek.toml`.
* Direct invocation: `python scripts/check_relative_imports.py [PATH...]`.
  When PATHs are supplied, only those files are scanned (any path
  outside `src/aeat/` is silently skipped — boundary `tests/` and
  `scripts/` are out of scope by design).

Boundaries: `tests/` and `scripts/` live outside the package and may
import `aeat.*` absolutely; this script does not scan them, even when
explicitly listed on the command line.

Known blind-spot: dynamic-import strings such as
``pytest.importorskip("aeat.X")`` or ``importlib.import_module("aeat.X")``
are NOT flagged because the AST sees them as plain string constants.
This is intentional — string-form module names are sometimes the
right tool (placeholder gates, plugin loaders), and a heuristic match
on every "aeat."-prefixed string would produce noise. New contributors
adding dynamic-import sites should prefer relative-equivalent helpers
where possible; reviewers should grep for `"aeat\\."` in any new code.

See `.vault/adr/2026-04-17-relative-imports-adr.md`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_AEAT = REPO_ROOT / "src" / "aeat"

# Sanity cap: any single Python source file larger than this is almost
# certainly not handwritten code (vendored blob, generated dump, mis-
# committed binary). Reject loudly rather than risk an OOM during
# pre-commit. The largest legitimate file under src/aeat/ is well under
# 200 kB; 2 MB gives generous headroom while still catching pathological
# inputs.
_MAX_SOURCE_BYTES = 2 * 1024 * 1024


def _scan_file(path: Path) -> tuple[list[tuple[int, str]], list[str]]:
    """Return (findings, errors) for absolute `aeat.*` imports in `path`.

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
            "landed in src/aeat/."
        )
        return findings, errors

    try:
        source = path.read_text(encoding="utf-8")
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
                if alias.name != "aeat" and not alias.name.startswith("aeat."):
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
        if node.module != "aeat" and not node.module.startswith("aeat."):
            continue
        names = ", ".join(alias.name + (f" as {alias.asname}" if alias.asname else "") for alias in node.names)
        findings.append((node.lineno, f"from {node.module} import {names}"))
    return findings, errors


def _resolve_targets(args: list[str]) -> list[Path]:
    """Pick the files to scan.

    With no args, walk every `*.py` under `src/aeat/`. With args, take
    the listed paths and keep only those inside `src/aeat/`. Paths
    outside `src/aeat/` (tests, scripts, env, etc.) are silently
    dropped because the mandate scopes there explicitly to absolute
    imports — surfacing them as "skipped" would be noise during a
    pre-commit run.
    """
    if not args:
        return sorted(SRC_AEAT.rglob("*.py"))

    targets: list[Path] = []
    src_aeat_resolved = SRC_AEAT.resolve()
    for raw in args:
        # Resolve relative to the current working directory — standard
        # CLI semantics. prek invokes hooks from the repo root, so this
        # also handles repo-root-relative paths correctly. Per Gemini
        # PR-review feedback on #162.
        candidate = Path(raw).resolve()
        if candidate.suffix != ".py":
            continue
        try:
            candidate.relative_to(src_aeat_resolved)
        except ValueError:
            continue
        if not candidate.is_file():
            continue
        targets.append(candidate)
    return targets


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]

    if not SRC_AEAT.is_dir():
        sys.stderr.write(f"src/aeat not found at {SRC_AEAT}\n")
        return 2

    targets = _resolve_targets(args)

    all_findings: list[tuple[Path, int, str]] = []
    all_errors: list[str] = []
    for path in targets:
        findings, errors = _scan_file(path)
        for lineno, rendered in findings:
            all_findings.append((path, lineno, rendered))
        all_errors.extend(errors)

    if all_errors:
        sys.stderr.write(
            "scripts/check_relative_imports.py: refusing to certify the tree because "
            f"{len(all_errors)} file(s) could not be scanned:\n"
        )
        for err in all_errors:
            sys.stderr.write(f"  {err}\n")
        sys.stderr.write("\n")

    if all_findings:
        sys.stderr.write(
            "Absolute `aeat.*` imports are banned inside src/aeat/ (#162).\n"
            "Use relative imports (`from .module import X` or `from ..sibling import Y`).\n"
            "See CLAUDE.md > 'Relative-Imports Mandate'.\n\n"
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
