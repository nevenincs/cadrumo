"""Ratchet: no module may publish a new name that nothing imports.

A name in ``__all__`` is a promise. One that no other module imports AND that
the reachability audit finds unused is a promise nothing collects: it cannot be
removed as ordinary dead code, because removal changes what the package
publishes, and it cannot be left silent, because it reads as supported. 368 of
them exist, which is a review nobody can finish in one sitting -- and while it
waits, nothing stops the number growing.

Both halves of that test matter. Counting every exported name no other module
imports yields 2247, most of them ordinary published API whose consumer is a
test or an external caller; a gate on THAT would fire on any new public
interface before its first importer landed, which is the wrong moment to argue
with an author. Intersecting with the audit narrows it to names that are
published, unimported, AND unreached -- the population actually under review.

This does not ask anyone to resolve the 368. It records them per module and
refuses a new one, which is the half that needs no decision. A name added to
``__all__`` today is an author's live choice, and the cheapest moment to ask
"who imports this?" is while they still remember why they exported it.

Consumption is deliberately strict: a name counts as consumed only when another
module from-imports it FROM the declaring module. Matching the bare name would
count same-named functions in unrelated packages, and this tree has many.

It fails in four directions, so paid-down debt is recorded rather than leaving
headroom:

* a module not in the baseline publishes an unconsumed name -- new debt;
* a recorded module publishes more than recorded -- growth;
* a recorded module publishes fewer -- progress that must be written down;
* a recorded module publishes none -- the entry is spent and must be removed.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dev.audit.unreachable_code import run_unreachable_code_scan

__all__ = ["ExportVerdict", "count_unconsumed", "evaluate"]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PACKAGE_ROOT = REPO_ROOT / "src" / "cadrumo"
_BASELINE = Path(__file__).with_suffix(".toml")


@dataclass(frozen=True, slots=True)
class ExportVerdict:
    """What the ratchet found, split by the direction each finding points."""

    added: dict[str, int]
    grown: dict[str, tuple[int, int]]
    shrunk: dict[str, tuple[int, int]]
    spent: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Whether every recorded count matches the tree exactly."""
        return not (self.added or self.grown or self.shrunk or self.spent)


def _declared_exports(tree: ast.Module) -> list[str]:
    """Return the string entries of a module-level ``__all__``."""
    for node in tree.body:
        for target in node.targets if isinstance(node, ast.Assign) else []:
            if isinstance(target, ast.Name) and target.id == "__all__":
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    return [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    return []


def _imported_pairs(tree: ast.Module) -> set[tuple[str, str]]:
    """Return (source module tail, imported name) for every from-import."""
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            tail = node.module.rsplit(".", 1)[-1]
            pairs.update((tail, alias.name) for alias in node.names)
    return pairs


def count_unconsumed(root: Path = _PACKAGE_ROOT, unused: set[tuple[str, str]] | None = None) -> dict[str, int]:
    """Return how many published names each module carries that nothing collects.

    A name counts only when it is exported, imported by no other module, AND
    reported unused by the reachability audit.
    """
    if unused is None:
        result = run_unreachable_code_scan(REPO_ROOT)
        unused = {(str(finding.path).replace("\\", "/"), finding.name) for finding in result.symbols}
    trees: dict[Path, ast.Module] = {}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue

    consumed: set[tuple[str, str]] = set()
    for tree in trees.values():
        consumed |= _imported_pairs(tree)

    counts: dict[str, int] = {}
    for path, tree in trees.items():
        unconsumed = sum(
            1
            for name in _declared_exports(tree)
            if (path.stem, name) not in consumed and (path.as_posix(), name) in unused
        )
        if unconsumed:
            counts[path.relative_to(root).as_posix()] = unconsumed
    return counts


def evaluate(root: Path = _PACKAGE_ROOT, baseline_path: Path = _BASELINE) -> ExportVerdict:
    """Compare the live unconsumed-export counts against the recorded baseline."""
    live = count_unconsumed(root)
    recorded: dict[str, int] = {}
    if baseline_path.exists():
        loaded = tomllib.loads(baseline_path.read_text(encoding="utf-8")).get("files", {})
        recorded = {str(path): int(count) for path, count in loaded.items()}

    added = {path: n for path, n in live.items() if path not in recorded}
    grown = {p: (live[p], recorded[p]) for p in live if p in recorded and live[p] > recorded[p]}
    shrunk = {p: (live[p], recorded[p]) for p in live if p in recorded and live[p] < recorded[p]}
    spent = tuple(sorted(p for p in recorded if p not in live))
    return ExportVerdict(added=added, grown=grown, shrunk=shrunk, spent=spent)


def main() -> int:
    """Report the verdict; exit 1 when the tree and the baseline disagree."""
    verdict = evaluate()
    if verdict.ok:
        return 0
    if verdict.added:
        total = sum(verdict.added.values())
        sys.stdout.write(f"{len(verdict.added)} module(s) newly publish a name nothing imports ({total}).\n")
        sys.stdout.write("Import it, or leave it out of __all__; do not add a line here:\n")
        for path, count in sorted(verdict.added.items()):
            sys.stdout.write(f"  + {path} ({count})\n")
    if verdict.grown:
        sys.stdout.write(f"{len(verdict.grown)} module(s) publish more than recorded:\n")
        for path, (now, was) in sorted(verdict.grown.items()):
            sys.stdout.write(f"  ^ {path}: {now} now, {was} recorded\n")
    if verdict.shrunk:
        sys.stdout.write(f"{len(verdict.shrunk)} module(s) publish fewer than recorded; lower the entry:\n")
        for path, (now, was) in sorted(verdict.shrunk.items()):
            sys.stdout.write(f"  v {path}: {now} now, {was} recorded\n")
    if verdict.spent:
        sys.stdout.write(f"{len(verdict.spent)} recorded module(s) publish none; remove the entry:\n")
        for path in verdict.spent:
            sys.stdout.write(f"  - {path}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
