"""Rewrite stale src/aeat path references inside .vault/ documents.

After the aeat-restructure layout move (#476), most vault docs still
reference the OLD flat layout (`src/aeat/errors/`, `aeat.formulas`,
etc.). The Tier-3 inline-update step rewrites those references in
place — the topic/decision is preserved, only the path token is
updated to match the new hexagonal layout.

The rewrite map is loaded from `scripts/restructure_rewrite_map.json`
and applied longest-match-first, both for dotted-Python references
(e.g. `aeat.formulas` -> `aeat.domain.formulas`) and for path-style
references (e.g. `src/aeat/formulas/` -> `src/aeat/domain/formulas/`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REWRITE_MAP_PATH = Path("scripts/restructure_rewrite_map.json")


def _load_rename_map(repo_root: Path) -> dict[str, str]:
    raw = json.loads((repo_root / REWRITE_MAP_PATH).read_text(encoding="utf-8"))
    return raw["rename"]


def _build_patterns(rename: dict[str, str]) -> list[tuple[re.Pattern[str], str]]:
    """Build longest-match-first patterns for both dotted + path forms."""
    # Sort longest-key-first so e.g. `aeat.financial.transactions` (if present)
    # would pre-empt `aeat.financial`.
    items = sorted(rename.items(), key=lambda kv: -len(kv[0]))
    patterns: list[tuple[re.Pattern[str], str]] = []
    for old, new in items:
        # Dotted form: `aeat.formulas` -> `aeat.domain.formulas`
        # Word-boundary on both sides to avoid matching `aeat.formulas2`.
        # Negative lookbehind to avoid matching when a longer prefix already matched.
        old_re = re.escape(old)
        patterns.append(
            (
                re.compile(rf"(?<![\w.]){old_re}(?![\w])"),
                new,
            )
        )
        # Path form: convert `aeat.X` -> `src/aeat/X/...` and `aeat/X/`
        old_path_dotted_only = old.split(".", 1)[1]  # strip leading "aeat."
        new_path_dotted_only = new.split(".", 1)[1]
        old_path = old_path_dotted_only.replace(".", "/")
        new_path = new_path_dotted_only.replace(".", "/")
        # `src/aeat/<old>/` (with trailing slash) -> `src/aeat/<new>/`
        patterns.append(
            (
                re.compile(rf"(?<![\w]){re.escape(f'src/aeat/{old_path}/')}"),
                f"src/aeat/{new_path}/",
            )
        )
        # `aeat/<old>/` (without `src/` prefix; relative path style)
        patterns.append(
            (
                re.compile(rf"(?<![\w]){re.escape(f'aeat/{old_path}/')}"),
                f"aeat/{new_path}/",
            )
        )
    return patterns


def _rewrite_text(text: str, patterns: list[tuple[re.Pattern[str], str]]) -> str:
    out = text
    for pat, repl in patterns:
        out = pat.sub(repl, out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--vault-dir",
        default=".vault",
        help="Vault root (default: .vault)",
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    rename = _load_rename_map(repo_root)
    patterns = _build_patterns(rename)

    vault = repo_root / args.vault_dir
    files_changed = 0
    files_scanned = 0

    for path in sorted(vault.rglob("*.md")):
        files_scanned += 1
        original = path.read_text(encoding="utf-8")
        rewritten = _rewrite_text(original, patterns)
        if rewritten != original:
            files_changed += 1
            rel = path.relative_to(repo_root).as_posix()
            print(f"{'(dry) ' if args.dry_run else ''}rewrite {rel}")
            if not args.dry_run:
                path.write_text(rewritten, encoding="utf-8")

    print(f"scanned={files_scanned} changed={files_changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
