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

* `just lint` — runs this after `ruff check` (see `justfile`).
* `prek run --all-files` — runs as a local hook (see `prek.toml`).

Boundaries: `tests/` and `scripts/` live outside the package and may
import `aeat.*` absolutely; this script does not scan them.

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


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, rendered) for every absolute `aeat.*` import in `path`."""
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    findings: list[tuple[int, str]] = []
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
    return findings


def _scan(root: Path) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    for path in sorted(root.rglob("*.py")):
        for lineno, rendered in _scan_file(path):
            findings.append((path, lineno, rendered))
    return findings


def main() -> int:
    if not SRC_AEAT.is_dir():
        sys.stderr.write(f"src/aeat not found at {SRC_AEAT}\n")
        return 2

    findings = _scan(SRC_AEAT)
    if not findings:
        return 0

    sys.stderr.write(
        "Absolute `aeat.*` imports are banned inside src/aeat/ (#162).\n"
        "Use relative imports (`from .module import X` or `from ..sibling import Y`).\n"
        "See CLAUDE.md > 'Relative-Imports Mandate'.\n\n"
    )
    for path, lineno, line in findings:
        rel = path.relative_to(REPO_ROOT)
        sys.stderr.write(f"{rel}:{lineno}: {line}\n")
    sys.stderr.write(f"\n{len(findings)} violation(s).\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
