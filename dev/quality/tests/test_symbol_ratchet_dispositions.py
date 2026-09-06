"""Gate: an intentional symbol disposition stays true and stays reviewable.

The symbol ratchet admits a deliberately kept symbol through an
``[[intentional]]`` entry, mirroring the module ratchet beside it. That
mechanism is the one place in this ratchet where a finding leaves the
comparison without being resolved, so it carries the strictest conditions: the
kind comes from the same closed enum, the rationale must name the reader that
justifies the keep, and the entry must still describe a live finding.

The failure it guards against is the one this tree has produced four times
already -- a sentence asserting a consumer that no longer consumes. A stale
disposition is worse than an unrecorded finding, because it reads as reviewed.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT
from ..unreachable_module_ratchet import IntentionalReachabilityKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BASELINE: Final[Path] = REPO_ROOT / "dev" / "quality" / "unused_symbol_ratchet.toml"
#: A rationale must point at a file, which is what makes the claim checkable.
_READER: Final[re.Pattern[str]] = re.compile(r"\b((?:dev|src)/[A-Za-z0-9_./-]+\.py)\b")


def _dispositions() -> list[dict[str, object]]:
    """Return the recorded intentional symbol dispositions.

    Raises:
        AssertionError: When the baseline declares no ``[[intentional]]``
            table at all.
    """
    data = tomllib.loads(_BASELINE.read_text(encoding="utf-8"))
    # A defaulting ``get`` reads a renamed or deleted table as "no
    # dispositions", and all four claims below then hold over an empty
    # list. The list may legitimately empty as keeps are retired, so the
    # guard belongs on the SOURCE rather than on the count: an empty list
    # must mean the table declared nothing, not that it was never found.
    assert "intentional" in data, (
        f"{_BASELINE.name} declares no [[intentional]] table, so every disposition "
        "claim in this module would hold over an empty list"
    )
    return list(data["intentional"])


def test_every_disposition_declares_a_closed_kind() -> None:
    """An open vocabulary would let any keep look deliberate."""
    for row in _dispositions():
        IntentionalReachabilityKind(str(row.get("kind", "")))


def test_every_disposition_names_a_reader_file_that_exists() -> None:
    """A rationale pointing at a file that is gone is a stale claim."""
    missing: list[str] = []
    for row in _dispositions():
        rationale = str(row.get("rationale", ""))
        readers = _READER.findall(rationale)
        if not readers:
            missing.append(f"{row.get('symbol')}: rationale names no reader file")
            continue
        missing.extend(
            f"{row.get('symbol')}: names {reader}, which does not exist"
            for reader in readers
            if not (REPO_ROOT / reader).is_file()
        )
    assert not missing, f"these dispositions no longer describe the tree: {missing}"


def test_every_named_reader_still_mentions_the_symbol() -> None:
    """The reader must still read it, not merely still exist.

    The vacuity floor beside the staleness check is the point, and it is
    borrowed from the module ratchet's equivalent gate: if the rationale
    format drifts so the reader pattern stops matching, every disposition
    would pass this silently at once. Counting the checks distinguishes
    'nothing is stale' from 'nothing was examined'.
    """
    stale: list[str] = []
    checked = 0
    for row in _dispositions():
        symbol = str(row.get("symbol", ""))
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])")
        for reader in _READER.findall(str(row.get("rationale", ""))):
            path = REPO_ROOT / reader
            if not path.is_file():
                continue
            checked += 1
            if not pattern.search(path.read_text(encoding="utf-8")):
                stale.append(f"{symbol}: {reader} no longer mentions it")
    assert not stale, f"these dispositions name a reader that stopped reading them: {stale}"
    assert checked >= len(_dispositions()), (
        f"only {checked} reader(s) were checked across {len(_dispositions())} disposition(s); "
        "below one per disposition the rationales have stopped being checkable evidence "
        "and this gate is inert rather than satisfied"
    )


def test_every_disposition_carries_a_substantive_rationale() -> None:
    """A keep asserted in a phrase is not a keep that was reasoned."""
    thin = [str(row.get("symbol")) for row in _dispositions() if len(str(row.get("rationale", ""))) < 120]
    assert not thin, f"these dispositions state no reasoning: {thin}"


def test_the_reader_pattern_matches_a_real_rationale() -> None:
    """Detector teeth: the pattern must find the file a rationale names."""
    assert _READER.findall("read by src/cadrumo/entrypoints/cli/tests/test_command_specs.py to check") == [
        "src/cadrumo/entrypoints/cli/tests/test_command_specs.py"
    ]


def test_the_reader_pattern_ignores_prose_without_a_path() -> None:
    """The guard: ordinary prose must not read as a reader claim."""
    assert _READER.findall("read by the conformance gate beside it") == []
