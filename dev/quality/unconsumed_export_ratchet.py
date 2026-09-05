"""Ratchet: no module may publish a new name that nothing imports.

A name in ``__all__`` is a promise. One that no other module imports AND that
the reachability audit reports unused is a promise nothing collects: it cannot
be removed as ordinary dead code, because removal changes what the package
publishes, and it cannot be left silent, because it reads as supported.

Both halves of that test matter. Unimported alone would flag ordinary published
API whose only consumer is a test or an external caller, and a gate on that
would fire on a new public interface before its first importer landed -- the
wrong moment to argue with an author. Intersecting with the audit narrows it to
names that are published, unimported AND unreached.

Resolving the recorded population is a published-surface decision for an owner.
This enforces only the half needing no decision: that it does not grow. The
cheapest moment to ask "who imports this?" is while the author still remembers
exporting it.

Consumption is deliberately strict, and matches the inventory in
``dev/audit/reachability_classification.toml`` so the two cannot disagree about
what they count. A name counts as consumed only when another NON-TEST module
from-imports it FROM the declaring module: matching the bare name would count
same-named functions in unrelated packages, of which this tree has many, and
counting a test importer would call a name collected that the product never
reaches.

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

from ..audit.unreachable_code import run_unreachable_code_scan

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
        if not isinstance(node, ast.Assign) or not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            return [
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
    return []


def _imported_pairs(tree: ast.Module) -> set[tuple[str, str]]:
    """Return (source module tail, imported name) for every from-import."""
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            tail = node.module.rsplit(".", 1)[-1]
            pairs.update((tail, alias.name) for alias in node.names)
    return pairs


def _audit_key(path: Path, root: Path) -> str:
    """Return the path spelling the reachability audit reports findings under.

    The audit keys on paths relative to the repository root. A caller scanning
    some other tree -- a test fixture, say -- has no repository above it, so the
    key falls back to the scanned root's parent, which is the same shape.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.relative_to(root.parent).as_posix()


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
        # Tests are excluded as publishers AND as consumers, matching the
        # inventory in dev/audit/reachability_classification.toml: a name whose
        # only importer is a test is not collected by the product, and the two
        # records must not disagree about what they are counting.
        if "__pycache__" in path.parts or "tests" in path.parts or path.name.startswith("test_"):
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
            if (path.stem, name) not in consumed and (_audit_key(path, root), name) in unused
        )
        if unconsumed:
            counts[path.relative_to(root).as_posix()] = unconsumed
    return counts


def evaluate(
    root: Path = _PACKAGE_ROOT,
    baseline_path: Path = _BASELINE,
    unused: set[tuple[str, str]] | None = None,
) -> ExportVerdict:
    """Compare the live unconsumed-export counts against the recorded baseline.

    ``unused`` is threaded through rather than always derived, so a caller
    scanning a fixture tree does not trigger a scan of the real repository --
    which would key its findings against the wrong root and take minutes.
    """
    live = count_unconsumed(root, unused)
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
