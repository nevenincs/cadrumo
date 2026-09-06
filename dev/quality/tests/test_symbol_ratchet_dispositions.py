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
    """Return the recorded intentional symbol dispositions."""
    data = tomllib.loads(_BASELINE.read_text(encoding="utf-8"))
    return list(data.get("intentional", ()))


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
    """The reader must still read it, not merely still exist."""
    stale: list[str] = []
    for row in _dispositions():
        symbol = str(row.get("symbol", ""))
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])")
        for reader in _READER.findall(str(row.get("rationale", ""))):
            path = REPO_ROOT / reader
            if not path.is_file():
                continue
            if not pattern.search(path.read_text(encoding="utf-8")):
                stale.append(f"{symbol}: {reader} no longer mentions it")
    assert not stale, f"these dispositions name a reader that stopped reading them: {stale}"


def test_every_disposition_carries_a_substantive_rationale() -> None:
    """A keep asserted in a phrase is not a keep that was reasoned."""
    thin = [str(row.get("symbol")) for row in _dispositions() if len(str(row.get("rationale", ""))) < 120]
    assert not thin, f"these dispositions state no reasoning: {thin}"


def test_the_reader_pattern_matches_a_real_rationale() -> None:
    """Detector teeth: the pattern must find the file a rationale names."""
    assert _READER.findall("read by dev/quality/clitui_ledger_capability_matrix.py to check") == [
        "dev/quality/clitui_ledger_capability_matrix.py"
    ]


def test_the_reader_pattern_ignores_prose_without_a_path() -> None:
    """The guard: ordinary prose must not read as a reader claim."""
    assert _READER.findall("read by the conformance gate beside it") == []
