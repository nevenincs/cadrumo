"""Ratchet: shipped code must not gain new citations of a Vaultspec rule slug.

The `.vault/` corpus and the `.vaultspec/` harness are removable development
scaffolding layered over the codebase, never part of it. The reference
direction is one-way: a vault document cites code by locator, and code never
cites the vault. A docstring that names ``aeat-architecture-boundaries`` reads,
to anyone without the harness checked out, as a reference to something that
does not exist.

The governing rule already says so, and already says what to do about the ones
already there: existing citations are migration debt, and removing them needs
an explicit repository-wide migration with validation rather than an
opportunistic sweep. What nothing enforced was the other half of that sentence
-- do not add new ones. Roughly 145 shipped modules carry a citation today, so
a gate that demanded zero would fail on day one and be switched off. This
records the count per file instead and refuses an increase.

It fails in four directions, because a baseline that only catches growth lets
paid-down debt go unrecorded:

* a file not in the baseline carries a citation -- new debt;
* a recorded file carries more than recorded -- growth;
* a recorded file carries fewer -- progress that must be written down, so the
  ratchet cannot silently drift back up later;
* a recorded file carries none -- the entry is spent and must be removed.

Slugs are read from the shipped rule sources rather than hardcoded, so
retiring or adding a rule needs no edit here.
"""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "CitationVerdict",
    "count_citations",
    "evaluate",
    "rule_slugs",
]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RULE_SOURCES = REPO_ROOT / ".vaultspec" / "rules"
_SHIPPED = REPO_ROOT / "src"
_BASELINE = Path(__file__).with_suffix(".toml")


@dataclass(frozen=True, slots=True)
class CitationVerdict:
    """What the ratchet found, split by the direction each finding points."""

    added: dict[str, int]
    grown: dict[str, tuple[int, int]]
    shrunk: dict[str, tuple[int, int]]
    spent: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Whether every recorded count matches the tree exactly."""
        return not (self.added or self.grown or self.shrunk or self.spent)


def rule_slugs(source: Path = _RULE_SOURCES) -> frozenset[str]:
    """Return every rule slug the project ships, from the rule filenames."""
    return frozenset(path.stem.removesuffix(".builtin") for path in source.glob("*.md") if path.stem != "README")


def count_citations(root: Path = _SHIPPED, slugs: frozenset[str] | None = None) -> dict[str, int]:
    """Return the number of rule-slug citations in each shipped Python file.

    A slug is counted only inside backticks, either as a literal ``slug`` or
    wrapped in a Sphinx role. The bare words also read as domain vocabulary in
    ordinary prose -- "the per-period no-silent-under-declaration warning" is a
    sentence about behaviour, not a citation -- and counting those would make
    the ratchet argue with English.
    """
    names = slugs if slugs is not None else rule_slugs()
    if not names:
        return {}
    alternation = "|".join(sorted(map(re.escape, names)))
    # Two spellings carry a citation. The literal ``slug`` form, and a Sphinx
    # role around it -- :func:`no-silent-under-declaration` -- which is a
    # citation wearing the syntax for a Python symbol, and was invisible to a
    # pattern that only looked for double backticks.
    pattern = re.compile(rf"``(?:{alternation})``|:[a-z]+:`(?:{alternation})`")
    counts: dict[str, int] = {}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        found = len(pattern.findall(text))
        if found:
            counts[path.relative_to(root).as_posix()] = found
    return counts


def evaluate(root: Path = _SHIPPED, baseline_path: Path = _BASELINE) -> CitationVerdict:
    """Compare the live citation counts against the recorded baseline."""
    live = count_citations(root)
    recorded: dict[str, int] = {}
    if baseline_path.exists():
        loaded = tomllib.loads(baseline_path.read_text(encoding="utf-8")).get("files", {})
        recorded = {str(path): int(count) for path, count in loaded.items()}

    added = {path: n for path, n in live.items() if path not in recorded}
    grown = {p: (live[p], recorded[p]) for p in live if p in recorded and live[p] > recorded[p]}
    shrunk = {p: (live[p], recorded[p]) for p in live if p in recorded and live[p] < recorded[p]}
    spent = tuple(sorted(p for p in recorded if p not in live))
    return CitationVerdict(added=added, grown=grown, shrunk=shrunk, spent=spent)


def main() -> int:
    """Report the verdict; exit 1 when the tree and the baseline disagree."""
    verdict = evaluate()
    if verdict.ok:
        return 0
    if verdict.added:
        total = sum(verdict.added.values())
        sys.stdout.write(f"{len(verdict.added)} shipped file(s) newly cite a rule slug ({total} citation(s)).\n")
        sys.stdout.write("Say it in the code's own terms; do not add a line here to make this pass:\n")
        for path, count in sorted(verdict.added.items()):
            sys.stdout.write(f"  + {path} ({count})\n")
    if verdict.grown:
        sys.stdout.write(f"{len(verdict.grown)} file(s) gained citations:\n")
        for path, (now, was) in sorted(verdict.grown.items()):
            sys.stdout.write(f"  ^ {path}: {now} now, {was} recorded\n")
    if verdict.shrunk:
        sys.stdout.write(f"{len(verdict.shrunk)} file(s) carry fewer than recorded; lower the entry:\n")
        for path, (now, was) in sorted(verdict.shrunk.items()):
            sys.stdout.write(f"  v {path}: {now} now, {was} recorded\n")
    if verdict.spent:
        sys.stdout.write(f"{len(verdict.spent)} recorded file(s) carry none; remove the entry:\n")
        for path in verdict.spent:
            sys.stdout.write(f"  - {path}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
