"""Gate: no TypeScript module in the repository holds more than ``MAX_PHYSICAL_LINES`` physical lines.

A module that size carries many responsibilities at once: a reader cannot hold
it, a reviewer cannot see what a change touches, and every edit collides with
another. The bound applies to every TypeScript module the repository keeps:
product code, scenario fixtures, stories, prototypes, specs and scripts alike,
under any root, not only the desktop's.

``MAX_PHYSICAL_LINES`` is the bound's only definition. The frontend's
generators receive it from their Python producers and refuse to write a module
past it, so a generated module is split by its generator and never by hand; the
Modelo generator also writes it to ``src/shell/moduleBound.json`` for the lint
rule. This gate measures what every generator committed as well.

What counts
-----------
Every ``.ts``, ``.tsx``, ``.mts`` and ``.cts`` file in the repository, found on
the filesystem under the repository's ignore rules, so installed dependencies
and ignored build output stay out. A physical line is a line of the file as
stored, blank lines and comments included, and a last line without its newline
counts. A line ends only at a line feed, a carriage return, or the two
together, as Git and editors count lines. Any other separator, including
U+2028, U+2029, vertical tab, form feed and next line, stays inside its line.
The ESLint ``max-lines`` rule also treats U+2028 and U+2029 as line breaks, so
on such a file the editor warns earlier than the gate fails. It never warns
later.

How to satisfy the gate
-----------------------
Split the module by responsibility into modules that each define their own
symbols, and point every consumer at the defining module. A barrel or
re-exporting module, or a line-count trick such as joining lines, does not
satisfy the intent of this gate. There is no allowance list, baseline or
exemption.

What this gate does not bound
-----------------------------
The module bound is the only size bound implemented. No check bounds a single
function, component or hook, so a module under the bound can still hold one
very large callable. Whether any callable policy should exist is an undecided
question. This gate neither implements one nor implies that one will follow.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from dev.paths import REPO_ROOT
from dev.source_tree import repository_files

TYPESCRIPT_SUFFIXES: Final[frozenset[str]] = frozenset({".ts", ".tsx", ".mts", ".cts"})
MAX_PHYSICAL_LINES: Final[int] = 1500


def typescript_modules(root: Path = REPO_ROOT) -> list[str]:
    """Every TypeScript module the repository at ``root`` keeps, relative to it."""
    return [relative for relative in repository_files(root) if Path(relative).suffix in TYPESCRIPT_SUFFIXES]


def physical_lines(path: Path) -> int:
    """The lines of the file as stored, a final line without its newline included."""
    return len(path.read_bytes().splitlines())


def oversized(root: Path = REPO_ROOT) -> list[tuple[str, int]]:
    """The modules under ``root`` longer than the bound, with their line counts."""
    return [
        (relative, lines)
        for relative in typescript_modules(root)
        if (lines := physical_lines(root / relative)) > MAX_PHYSICAL_LINES
    ]


def main(root: Path = REPO_ROOT) -> int:
    """Print every module over the bound and return the process exit status.

    A walk that finds no TypeScript module at all is refused rather than
    reported clean, because this repository keeps TypeScript and an empty
    population means the walk did not read it.
    """
    modules = typescript_modules(root)
    if not modules:
        print(f"found no TypeScript module under {root}, so nothing was measured", file=sys.stderr)
        return 1
    found = oversized(root)
    for relative, lines in found:
        print(f"{relative}: {lines} physical lines (bound {MAX_PHYSICAL_LINES})")
    if found:
        print(f"{len(found)} of {len(modules)} TypeScript modules exceed {MAX_PHYSICAL_LINES} physical lines")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
