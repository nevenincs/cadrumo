"""Ratchet: no shipped module may gain a docstring reference that names nothing.

The screen beside this file finds them; this refuses new ones. A Sphinx role is
a claim that the named symbol exists, and nothing checked that claim, so it
routinely outlived the symbol -- a rename updated the code and left the prose,
and a reader who followed it landed on something gone. That is worse than no
documentation, because it is confidently wrong.

The population went from 87 to 4. What is left is not debt: each of the four is
an accurate statement about the PAST, naming a module or method that correctly
no longer exists. ``core.decimal.formatting`` records that it consolidated the
copies that "previously lived in" three now-absent modules, and
``secure_bound_repository`` explains why two read paths were merged by naming
the method that used to be one of them. Rewriting either would turn a true
sentence about history into a false one about the present -- an earlier sweep
did exactly that and was reverted.

So the baseline is not a debt ledger to burn down. It is the set of references
that are correct BECAUSE they name something absent, and the gate exists to
keep any other kind from joining them. It fails in four directions, so that
paid-down debt is recorded rather than leaving headroom:

* a file not in the baseline carries a dangling reference -- new debt;
* a recorded file carries more than recorded -- growth;
* a recorded file carries fewer -- progress that must be written down;
* a recorded file carries none -- the entry is spent and must be removed.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .docstring_reference_targets import _PACKAGE_ROOT, dangling_references

__all__ = ["ReferenceVerdict", "count_dangling", "evaluate"]

_BASELINE = Path(__file__).with_suffix(".toml")


@dataclass(frozen=True, slots=True)
class ReferenceVerdict:
    """What the ratchet found, split by the direction each finding points."""

    added: dict[str, int]
    grown: dict[str, tuple[int, int]]
    shrunk: dict[str, tuple[int, int]]
    spent: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Whether every recorded count matches the tree exactly."""
        return not (self.added or self.grown or self.shrunk or self.spent)


def count_dangling(root: Path = _PACKAGE_ROOT) -> dict[str, int]:
    """Return the number of dangling docstring references in each module."""
    counts: dict[str, int] = {}
    for finding in dangling_references(root):
        counts[finding.module] = counts.get(finding.module, 0) + 1
    return counts


def evaluate(root: Path = _PACKAGE_ROOT, baseline_path: Path = _BASELINE) -> ReferenceVerdict:
    """Compare the live dangling counts against the recorded baseline."""
    live = count_dangling(root)
    recorded: dict[str, int] = {}
    if baseline_path.exists():
        loaded = tomllib.loads(baseline_path.read_text(encoding="utf-8")).get("files", {})
        recorded = {str(path): int(count) for path, count in loaded.items()}

    added = {path: n for path, n in live.items() if path not in recorded}
    grown = {p: (live[p], recorded[p]) for p in live if p in recorded and live[p] > recorded[p]}
    shrunk = {p: (live[p], recorded[p]) for p in live if p in recorded and live[p] < recorded[p]}
    spent = tuple(sorted(p for p in recorded if p not in live))
    return ReferenceVerdict(added=added, grown=grown, shrunk=shrunk, spent=spent)


def main() -> int:
    """Report the verdict; exit 1 when the tree and the baseline disagree."""
    verdict = evaluate()
    if verdict.ok:
        return 0
    if verdict.added:
        total = sum(verdict.added.values())
        sys.stdout.write(f"{len(verdict.added)} module(s) newly name something absent ({total} reference(s)).\n")
        sys.stdout.write("Name what exists, or say it without a role; do not add a line here:\n")
        for path, count in sorted(verdict.added.items()):
            sys.stdout.write(f"  + {path} ({count})\n")
    if verdict.grown:
        sys.stdout.write(f"{len(verdict.grown)} module(s) gained dangling references:\n")
        for path, (now, was) in sorted(verdict.grown.items()):
            sys.stdout.write(f"  ^ {path}: {now} now, {was} recorded\n")
    if verdict.shrunk:
        sys.stdout.write(f"{len(verdict.shrunk)} module(s) carry fewer than recorded; lower the entry:\n")
        for path, (now, was) in sorted(verdict.shrunk.items()):
            sys.stdout.write(f"  v {path}: {now} now, {was} recorded\n")
    if verdict.spent:
        sys.stdout.write(f"{len(verdict.spent)} recorded module(s) carry none; remove the entry:\n")
        for path in verdict.spent:
            sys.stdout.write(f"  - {path}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
