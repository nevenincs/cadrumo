"""Strip dev-process metadata (wave/phase/cluster) from source files.

Per project mandate: wave/phase markers are dev-process metadata for vault
docs and commit messages only — source code/docstrings must describe the
architecture, not the delivery cadence.

This script applies a deterministic regex sweep across `src/aeat/` to remove
common dev-process labels while preserving the technical substance that
follows them. Examples:

  "Wave 51 H1: NBSP tolerance"   -> "NBSP tolerance"
  "Wave-6 tests: redaction"      -> "tests: redaction"
  "(wave 29 HIGH-3)"             -> ""
  "(EPIC #305 cluster D)"        -> "(EPIC #305)"

The script is line-scoped: only lines that contain a delivery-cadence label
are rewritten. Non-matching lines are left byte-for-byte unchanged. Run from
a clean tree, then `git diff` to review before committing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Sub-tag suffix item: "H1", "H-1", "MEDIUM-3", "M2", "L4", "HIGH-2", etc.
_TAG_ITEM = r"[A-Z]+\d*(?:[\s\-]\d+)?"
# Optional sub-tag list: " H1" or " HIGH-1/HIGH-2" or " MEDIUM-3/HIGH-1"
_TAG = rf"(?:\s+{_TAG_ITEM}(?:/{_TAG_ITEM})*)?"

# Patterns to strip. Order matters — most-specific first.
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # "(wave 29 HIGH-3)" or "(wave-29)" — fully parenthetical, drop with parens.
    (
        "parenthetical-wave-only",
        re.compile(rf"\s*\((?:pre-)?wave[\s\-_]*\d+[A-Za-z]?{_TAG}\)", re.IGNORECASE),
        "",
    ),
    # "(phase 2)" parenthetical
    (
        "parenthetical-phase-only",
        re.compile(r"\s*\(phase\s*\d+(?:[\s\-_][A-Za-z0-9\-]+)?\)", re.IGNORECASE),
        "",
    ),
    # "(cluster A)" parenthetical
    (
        "parenthetical-cluster-only",
        re.compile(r"\s*\(cluster\s+[A-Za-z]\b\)", re.IGNORECASE),
        "",
    ),
    # "(EPIC #305 cluster D)" — drop only the " cluster D" inside larger parens.
    (
        "embedded-cluster-in-parens",
        re.compile(r"(\([^)]*?)\s+cluster\s+[A-Za-z]\b([^)]*\))", re.IGNORECASE),
        r"\1\2",
    ),
    # Lead-in label with colon: "Wave 51 H1: ", "Wave-6: " — drop label, keep substance.
    (
        "leadin-wave-colon",
        re.compile(rf"\b(?:pre-)?wave[\s\-_]*\d+[A-Za-z]?{_TAG}:\s*", re.IGNORECASE),
        "",
    ),
    # "Wave 27 migrated" — bare lead-in followed by lower-case verb.
    (
        "leadin-wave-bare",
        re.compile(rf"\b(?:pre-)?wave[\s\-_]*\d+[A-Za-z]?{_TAG}\s+(?=[a-z])", re.IGNORECASE),
        "",
    ),
    # Inline "wave 51 H1" / "wave-51"
    (
        "inline-wave",
        re.compile(rf"\b(?:pre-)?wave[\s\-_]*\d+[A-Za-z]?{_TAG}\b", re.IGNORECASE),
        "",
    ),
    (
        "leadin-phase-colon",
        re.compile(r"\bphase\s*\d+:\s*", re.IGNORECASE),
        "",
    ),
    (
        "inline-phase",
        re.compile(r"\bphase\s*\d+\b", re.IGNORECASE),
        "",
    ),
    (
        "inline-cluster",
        re.compile(r"\bcluster\s+[A-Za-z]\b(?!\s*(?:in|of)\b)", re.IGNORECASE),
        "",
    ),
]

SKIP_PATHS = {
    "scripts/sanitize_dev_metadata.py",
}

_LINE_CUE_RE = re.compile(r"\b(?:pre-)?wave[\s\-_]*\d+|\bphase\s*\d+|\bcluster\s+[A-Za-z]\b", re.IGNORECASE)

# After substitutions, tighten the residue. ORDER matters: paren tidying first.
_CLEANUP_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # "(EPIC #305 )" -> "(EPIC #305)" — strip trailing space inside parens.
    (re.compile(r"(\([^()\n]*?)\s+\)"), r"\1)"),
    # Collapse two-or-more spaces (NOT touching indentation).
    # We apply this only on the body, not on indentation, in code below.
]


def _normalize_line(line: str) -> str:
    """Apply patterns + targeted cleanup to one line. Preserves indentation."""
    out = line
    for _name, pat, repl in PATTERNS:
        out = pat.sub(repl, out)
    if out == line:
        return line  # no rewrite — preserve byte-for-byte

    # Apply paren tidying (in/around content already substituted).
    for pat, repl in _CLEANUP_PATTERNS:
        out = pat.sub(repl, out)

    # Collapse double-spaces only on the body (preserve indent).
    leading_match = re.match(r"^(\s*)", out)
    leading = leading_match.group(1) if leading_match else ""
    body = out[len(leading) :]
    body = re.sub(r"  +", " ", body)
    # Tidy "# : foo" / "# . foo" leftovers in comments.
    body = re.sub(r"^(#\s*)[:.](\s)", r"\1\2", body)
    # "foo — ." / "foo - ." -> "foo."
    body = re.sub(r"\s+[—-]\s*([\.\,])", r"\1", body)
    # "foo: ." -> "foo."
    body = re.sub(r":\s+\.", ".", body)
    # ``"""."""`` collapsed prose — leave as-is; rare and harmless.
    out = leading + body
    return out


def _normalize(text: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if _LINE_CUE_RE.search(line):
            out_lines.append(_normalize_line(line))
        else:
            out_lines.append(line)
    return "".join(out_lines)


def _should_process(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root).as_posix()
    if rel in SKIP_PATHS:
        return False
    if not rel.startswith("src/aeat/"):
        return False
    return path.suffix == ".py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    files_changed = 0
    files_scanned = 0

    for path in sorted((repo_root / "src" / "aeat").rglob("*.py")):
        if not _should_process(path, repo_root):
            continue
        files_scanned += 1
        original = path.read_text(encoding="utf-8")
        rewritten = _normalize(original)
        if rewritten != original:
            files_changed += 1
            rel = path.relative_to(repo_root).as_posix()
            print(f"{'(dry) ' if args.dry_run else ''}rewrite {rel}")  # noqa: T201
            if not args.dry_run:
                path.write_text(rewritten, encoding="utf-8")

    print(f"scanned={files_scanned} changed={files_changed}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
