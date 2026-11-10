"""Report the year-literal and complexity findings a branch adds relative to its merge-base.

The repository forbids resolving or invoking the Git executable from developer
tools, so this tool reads no history. The caller prepares three explicit
inputs outside it:

* ``--base-tree``: a directory holding the merge-base version of the files;
* ``--head-tree``: a directory holding the branch version of the files;
* ``--paths-from``: a repository-relative changed-path manifest, one path per
  line, naming the files the branch added or modified.

Example, with the merge-base worktree and the manifest prepared by the lander::

    python -m dev.quality.branch_gate_delta --base-tree X:/code/merge-base-worktree
        --head-tree X:/code/branch-worktree --paths-from changed-paths.txt

Only Python and TypeScript paths are read. A path missing from the base tree is
a new file, so all of its findings are added; a path missing from the head tree
is skipped. Year literals use the year gate's rules over the same governed
population. Complexity uses the complexity gate's detectors and threshold over
production Python only (tests, bundled data and files outside the first-party
roots are not measured). A complexity finding is identified by file, kind and
callable, so a pre-existing hit whose score merely changes is not added, while a
new callable, a new kind or a newly appearing hit is.

Exit status is 1 when any finding is added or a scan cannot complete, else 0; a
branch that only removes findings passes.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from dev.audit import complexity
from dev.ci.change_scope import read_changed_files
from dev.exit_codes import FAILED, OK
from dev.first_party_source import FIRST_PARTY_ROOTS, is_production_source
from dev.quality import year_literals

__all__ = ["GateDelta", "compute_delta", "main"]

_SOURCE_SUFFIXES = year_literals.PYTHON_SUFFIXES | year_literals.TYPESCRIPT_SUFFIXES
_FIRST_PARTY_PREFIXES = tuple(f"{root}/" for root in FIRST_PARTY_ROOTS)


@dataclass(frozen=True)
class GateDelta:
    """The findings a branch adds and removes, as sorted printable lines."""

    added: tuple[str, ...]
    removed: tuple[str, ...]


def _year_findings(tree: Path, paths: Sequence[str]) -> Counter[tuple[str, str, str]]:
    """Count year findings by file, rule and text, so a moved line is not a change."""
    found: Counter[tuple[str, str, str]] = Counter()
    for relative in paths:
        file = tree / relative
        if relative.startswith(year_literals.AUTHORITY_DATA_ROOTS) or not file.is_file():
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        found.update((f.path, f.rule, f.text) for f in year_literals.findings_for(relative, text))
    return found


def _complexity_findings(tree: Path, paths: Sequence[str]) -> dict[tuple[str, str, str], str]:
    """Map each complexity finding's file, kind and callable to its rendered line."""
    files = tuple(
        tree / relative
        for relative in paths
        if relative.startswith(_FIRST_PARTY_PREFIXES) and is_production_source(relative) and (tree / relative).is_file()
    )
    if not files:
        return {}
    scan = complexity.measure_population(files, cognitive_threshold=complexity.DEFAULT_COGNITIVE_THRESHOLD)
    prefix = f"{tree.as_posix()}/"
    found: dict[tuple[str, str, str], str] = {}
    for kind, hits in (
        ("cyclomatic", scan.cyclomatic),
        ("maintainability", scan.maintainability),
        ("cognitive", scan.cognitive),
        ("length", scan.lengths),
    ):
        for hit in hits:
            found[(hit.path.removeprefix(prefix), kind, getattr(hit, "name", ""))] = (
                f"{kind}: {hit.render().replace(prefix, '')}"
            )
    return found


def _year_lines(findings: Counter[tuple[str, str, str]]) -> list[str]:
    return [f"year literal: {path}: {rule}: {text}" for path, rule, text in sorted(findings.elements())]


def compute_delta(base_tree: Path, head_tree: Path, paths: Sequence[str]) -> GateDelta:
    """Compare both gates' findings on ``paths`` between the two trees."""
    selected = [p for p in paths if Path(p).suffix in _SOURCE_SUFFIXES]
    base_years = _year_findings(base_tree, selected)
    head_years = _year_findings(head_tree, selected)
    base_cx = _complexity_findings(base_tree, selected)
    head_cx = _complexity_findings(head_tree, selected)
    added = _year_lines(head_years - base_years) + [head_cx[key] for key in sorted(head_cx.keys() - base_cx.keys())]
    removed = _year_lines(base_years - head_years) + [base_cx[key] for key in sorted(base_cx.keys() - head_cx.keys())]
    return GateDelta(tuple(added), tuple(removed))


def _print_section(title: str, lines: Sequence[str]) -> None:
    print(f"{title}: {len(lines)}")
    for line in lines:
        print(f"  {line}")


def main(argv: Sequence[str] | None = None) -> int:
    """Print the added and removed findings and return 1 when any finding is added."""
    parser = argparse.ArgumentParser(description="Report gate findings a branch adds or removes.")
    parser.add_argument("--base-tree", type=Path, required=True, help="Directory holding the merge-base files.")
    parser.add_argument("--head-tree", type=Path, required=True, help="Directory holding the branch files.")
    parser.add_argument("--paths-from", type=Path, required=True, help="Changed-path manifest, one path per line.")
    args = parser.parse_args(argv)
    for tree in (args.base_tree, args.head_tree):
        if not tree.is_dir():
            print(f"{tree} is not a directory", file=sys.stderr)
            return FAILED
    try:
        delta = compute_delta(args.base_tree.resolve(), args.head_tree.resolve(), read_changed_files(args.paths_from))
    except (OSError, ValueError, complexity.IncompleteScanError) as exc:
        print(f"scan incomplete, not clean: {exc}", file=sys.stderr)
        return FAILED
    _print_section("added", delta.added)
    _print_section("removed", delta.removed)
    return FAILED if delta.added else OK


if __name__ == "__main__":
    raise SystemExit(main())
