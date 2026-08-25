"""Report open plan rows whose scope clause names a path that no longer exists.

A plan row is falsified by a CORRECT change made elsewhere: someone relocates a
module, and every row in every other plan that named its old path is now wrong.
Nobody updates them, because nobody doing the relocation is reading those plans
and the author has moved on. A stale row reads exactly like a fresh one.

This is maintainer-invoked and is deliberately NOT a pytest gate. ``testpaths``
covers ``src/cadrumo`` and one packaging module, so a test placed under
``dev/tests/`` would be reached by no lane -- a gate nobody runs is
indistinguishable from a gate that does not exist, and installing one here would
assert coverage this repository does not have.

==========================================================
Why a naive existence check is worse than none
==========================================================

Most missing scope paths are CREATE TARGETS: a row that authors a gate names the
file it will produce, and that file is correctly absent until the row runs.
Reporting those makes the output mostly false, and an author who meets thirteen
false positives stops reading it -- which is worse than never having built it.

So a path is reported only when NO row in the SAME plan names it as something to
create. That is a dependency test rather than a verb test, and the difference is
load-bearing: a verb classifier reads "Prove the retry journeys;
``test_x.py``" as expecting an existing file, when the row's whole job is to
write it. Measured on this repository, the verb heuristic reported eleven and
the dependency test reported one.

==========================================================
What this cannot see, which is the larger half
==========================================================

It checks PATHS. It cannot touch a row whose PROSE premise is falsified while
every path still resolves -- an ignore directive that stopped being inert, a
conversion that cannot fire on its target, a block that was never blocked. Those
cost more time than stale paths do, and they are invisible here. A check that
covers the cheap half of a class is dangerous in proportion to how reliably it
runs, so the limit is printed with every report rather than documented once.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT

_ROOT: Final[Path] = REPO_ROOT
_PLANS: Final[Path] = _ROOT / ".vault/plan"

_ROW: Final[re.Pattern[str]] = re.compile(r"^- \[( |x)\] `([A-Z0-9.]+)` - (.*)$")
_PATH: Final[re.Pattern[str]] = re.compile(r"(?:src|dev|docs|\.github|\.vault)/[A-Za-z0-9_./-]+")
#: A row naming a path under one of these verbs is PRODUCING it, so its absence
#: is the row's remaining work rather than a stale reference.
_CREATES: Final[re.Pattern[str]] = re.compile(
    r"\b(author|add|create|write|introduce|scaffold|build|land|declare|publish|generate|extend|emit|prove|fail)\b",
    re.IGNORECASE,
)


def _scope_paths(scope: str) -> set[str]:
    """Return every repo-relative path token in one scope clause.

    Extracted by pattern rather than by splitting on separators: scope clauses
    mix comma lists, the word "and", and trailing prose, and a splitter tuned to
    one of those silently mangles the others.
    """
    return {match.rstrip("./") for match in _PATH.findall(scope)}


def stale_rows() -> list[tuple[str, str, str]]:
    """Return ``(plan, row id, missing path)`` for every open row's dead scope path."""
    findings: list[tuple[str, str, str]] = []
    for plan in scan_directory(_PLANS, pattern="*.md"):
        parsed: list[tuple[str, str, str, set[str]]] = []
        for line in plan.read_text(encoding="utf-8", errors="replace").split("\n"):
            row = _ROW.match(line)
            if row is None or ";" not in row.group(3):
                continue
            action, scope = row.group(3).rsplit(";", 1)
            parsed.append((row.group(1), row.group(2), action, _scope_paths(scope)))
        produced = {path for _, _, action, paths in parsed if _CREATES.search(action) for path in paths}
        for state, row_id, _, paths in parsed:
            if state != " ":
                continue
            findings.extend(
                (plan.name, row_id, path)
                for path in sorted(paths)
                if not (_ROOT / path).exists() and path not in produced
            )
    return findings


def main() -> int:
    """Print the stale rows and return non-zero when any survive."""
    findings = stale_rows()
    for plan, row_id, path in findings:
        print(f"{plan}\t{row_id}\t{path}")
    print(f"\n{len(findings)} open row(s) name a scope path that does not exist.", file=sys.stderr)
    print(
        "PATHS ONLY. A row whose prose premise is falsified while its paths still resolve is invisible to this report.",
        file=sys.stderr,
    )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
