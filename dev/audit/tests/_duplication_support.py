"""Shared clone-record readers for the duplication gates.

Underscore-prefixed so it is never collected as a test module. Holds what both
lanes need: the repo root, the ``where`` line parser, and the recorded-vs-observed
disposition readers. The lane-specific pieces -- the npx probe for the live scan,
the synthetic defect fixtures for the parser checks -- stay with their own modules.
"""

from __future__ import annotations

import re
import tomllib
from collections import Counter
from collections.abc import Sequence

from ..._paths import REPO_ROOT
from ..duplication import (
    CloneGroup,
)

_REPO_ROOT = REPO_ROOT


_WHERE_PATH = re.compile(r"^-?\s*(.+?\.py) \[")

_DISPOSITIONS_PATH = _REPO_ROOT / "dev" / "audit" / "duplication_dispositions.toml"

# The classification vocabulary the record's own header defines. Held here so
# the parsing gates check membership against one list rather than each
# restating it, and so adding a classification is a deliberate edit.
_CLASSIFICATIONS = frozenset(
    {
        "cluster-owned",
        "intentional",
        "advisory-residue",
        "actionable",
    }
)


def _load_dispositions() -> dict[str, object]:
    """Parse the committed disposition record."""
    return tomllib.loads(_DISPOSITIONS_PATH.read_text(encoding="utf-8"))


def _paths_from_where(entries: list[str]) -> frozenset[str]:
    """Extract the bare file paths a disposition's ``where`` list names."""
    paths = set()
    for entry in entries:
        match = _WHERE_PATH.match(entry)
        assert match, f"disposition `where` entry has no parseable path: {entry!r}"
        paths.add(match.group(1))
    return frozenset(paths)


def _paths_from_group(group: CloneGroup) -> frozenset[str]:
    """Extract the bare file paths a live ``CloneGroup``'s console block names.

    ``CloneGroup.lines`` renders relative to the repository root
    (``src/cadrumo/...``), while the dispositions file records paths relative
    to ``src/cadrumo/`` -- the same convention its own header states.
    """
    paths = set()
    for line in group.lines[1:]:
        stripped = line.strip()
        match = _WHERE_PATH.match(stripped)
        if not match:
            continue
        path = match.group(1)
        paths.add(path.removeprefix("src/cadrumo/"))
    return frozenset(paths)


def _recorded_dispositions() -> Counter[frozenset[str]]:
    """Count how many clone groups the dispositions file records per file-set."""
    dispositions = _load_dispositions()
    return Counter(_paths_from_where(group["where"]) for group in dispositions.get("group", ()))


def _uncovered_groups(groups: Sequence[CloneGroup], recorded: Counter[frozenset[str]]) -> list[CloneGroup]:
    """Return the observed groups exceeding what the record accounts for.

    Coverage is a MULTISET comparison, not set membership. A self-clone names
    one file twice, so its file-set collapses to a single path; under a plain
    set membership test any second, unrelated clone group inside that same file
    matched the first one's entry and passed unseen. Comparing how MANY groups
    each file-set carries closes that hole while still keying on paths rather
    than line spans, which drift on every unrelated edit.

    Under-observing is not a failure: a group the record still carries but the
    scan no longer sees is a landed consolidation, which is progress.
    """
    observed = Counter(_paths_from_group(group) for group in groups)
    surplus = {paths: count - recorded[paths] for paths, count in observed.items() if count > recorded[paths]}
    uncovered: list[CloneGroup] = []
    for group in groups:
        paths = _paths_from_group(group)
        if surplus.get(paths, 0) > 0:
            uncovered.append(group)
            surplus[paths] -= 1
    return uncovered
