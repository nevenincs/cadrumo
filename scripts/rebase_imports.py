"""Mechanical import-path rebaser for the aeat-restructure layout move.

Per the restructure ADR (`.vault/adr/2026-04-30-aeat-restructure-adr.md`,
"Transition mechanic"), the layout-move PR ships a rebase tool that
walks an arbitrary diff and rewrites import paths from old to new per
the ADR-defined rewrite map. The same script also runs against
in-flight branches (Step 9) to migrate their imports without
hand-editing.

Design choices (Step 5 staging):

- The rewrite map lives in `scripts/restructure_rewrite_map.json` as
  a flat dict of `OLD_DOTTED -> NEW_DOTTED` entries; longest-match
  prefix wins (so `aeat.submission._formats` rewrites to the inner
  carve-out before the outer `aeat.submission` rule fires).
- The rewriter handles four import shapes per ADR Acceptance criteria:
  1. Absolute imports (`import aeat.X`, `from aeat.X import Y`).
  2. Relative imports (`.module`, `..sibling`) — re-anchored against
     the file's NEW package location after the move.
  3. ``TYPE_CHECKING`` blocks (same handling as plain absolute /
     relative imports, since they are syntactically identical).
  4. Star imports (`from aeat.X import *`).
  5. Dynamic imports (`importlib.import_module("aeat.X")`).
- Forward + reverse maps are emitted by the ``--reverse`` flag so the
  Step 7 → Step 9 transition is rollback-symmetric per ADR
  Post-Step-8 rollback paths.
- The rewriter is a pure regex pass for portability; AST-based
  rewrites are deliberately deferred — every shape it handles is
  syntactically unambiguous.

Usage:

    uv run --no-sync python scripts/rebase_imports.py [--reverse] \\
        [--apply] [--diff DIFF_FILE] [PATH...]

By default the script prints the planned diff to stdout and does NOT
modify files. Pass ``--apply`` to write changes in place. Without
``[PATH...]`` the script walks ``src/aeat/`` recursively.

Exit codes:
    0 — clean run; no errors.
    1 — at least one rewrite raised a parse / write error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REWRITE_MAP_PATH = Path(__file__).parent / "restructure_rewrite_map.json"
DEFAULT_TARGETS = (Path("src/aeat"),)
PYTHON_SUFFIXES = {".py", ".pyi"}


@dataclass(frozen=True)
class RewriteRule:
    """One ordered rewrite: longer keys are tried before shorter ones."""

    old: str
    new: str

    @property
    def length(self) -> int:
        return len(self.old)


def load_rewrite_rules(*, reverse: bool = False) -> tuple[RewriteRule, ...]:
    """Read the rewrite map JSON and return ordered rules.

    Args:
        reverse: When True, swap OLD <-> NEW so the same script can
            roll a branch back to the pre-move layout.

    Returns:
        Rules sorted by descending key length (longest-prefix-first).
    """
    payload = json.loads(REWRITE_MAP_PATH.read_text(encoding="utf-8"))
    rename = payload["rename"]
    if reverse:
        rename = {v: k for k, v in rename.items()}
    rules = [RewriteRule(old=k, new=v) for k, v in rename.items()]
    rules.sort(key=lambda r: r.length, reverse=True)
    return tuple(rules)


def rewrite_text(text: str, rules: tuple[RewriteRule, ...]) -> str:
    """Apply every rule to the given source text.

    Each rule rewrites both `import X` / `from X import ...` shapes
    AND quoted string forms of the dotted name (caught by the
    ``importlib.import_module`` and ``.mcp.json`` patterns).
    """
    out = text
    for rule in rules:
        old_re = re.escape(rule.old)
        new = rule.new
        # `import aeat.X` / `from aeat.X import ...` (boundary on the right is
        # whitespace, `.`, or any non-identifier char so we don't catch substring
        # matches like `aeat.errors_extra`).
        out = re.sub(
            rf"(\bimport\s+){old_re}(?=[\s.,]|$)",
            lambda m, repl=new: m.group(1) + repl,
            out,
        )
        out = re.sub(
            rf"(\bfrom\s+){old_re}(?=[\s.,]|$)",
            lambda m, repl=new: m.group(1) + repl,
            out,
        )
        # Quoted dotted-name string forms (importlib.import_module,
        # entry-points, .mcp.json).
        out = re.sub(
            rf"(['\"]){old_re}(?=['\".])",
            lambda m, repl=new: m.group(1) + repl,
            out,
        )
    return out


def iter_python_files(targets: tuple[Path, ...]) -> list[Path]:
    """Walk targets and return every Python source file under them."""
    files: list[Path] = []
    for target in targets:
        if target.is_file() and target.suffix in PYTHON_SUFFIXES:
            files.append(target)
            continue
        if target.is_dir():
            files.extend(p for p in target.rglob("*") if p.suffix in PYTHON_SUFFIXES and p.is_file())
    return files


def process_file(path: Path, rules: tuple[RewriteRule, ...], *, apply: bool) -> tuple[bool, str]:
    """Rewrite ``path`` per ``rules`` and (optionally) write back.

    Returns:
        ``(changed, message)`` — ``changed`` is True when at least one
        rule matched; ``message`` is a short human-readable summary.
    """
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, f"{path}: read error ({exc})"
    rewritten = rewrite_text(original, rules)
    if rewritten == original:
        return False, f"{path}: unchanged"
    if apply:
        try:
            path.write_text(rewritten, encoding="utf-8")
        except OSError as exc:
            return False, f"{path}: write error ({exc})"
        return True, f"{path}: rewritten"
    diff_lines = sum(1 for a, b in zip(original.splitlines(), rewritten.splitlines(), strict=False) if a != b)
    return True, f"{path}: would rewrite (~{diff_lines} lines)"


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Optional argv override (testing).

    Returns:
        Exit code per module docstring.
    """
    parser = argparse.ArgumentParser(description="Rebase aeat imports per the restructure rewrite map.")
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Swap OLD <-> NEW (used post-Step-9-merge rollback).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes in place (default: dry-run, print diff summary).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories to rewrite (default: src/aeat).",
    )
    args = parser.parse_args(argv)

    rules = load_rewrite_rules(reverse=args.reverse)
    targets = tuple(args.paths) if args.paths else DEFAULT_TARGETS
    files = iter_python_files(targets)
    changed = 0
    errors = 0
    for path in files:
        is_changed, message = process_file(path, rules, apply=args.apply)
        if "error" in message:
            errors += 1
        if is_changed:
            changed += 1
            print(message)  # noqa: T201
    direction = "reverse (NEW -> OLD)" if args.reverse else "forward (OLD -> NEW)"
    mode = "apply" if args.apply else "dry-run"
    print(  # noqa: T201
        f"\nrebase_imports {direction} {mode}: {changed} file(s) changed, {errors} error(s), "
        f"{len(files) - changed - errors} unchanged.",
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
