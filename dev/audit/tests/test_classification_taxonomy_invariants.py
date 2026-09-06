"""Gate: every classified finding resolves into exactly one class.

The governing decision states that every finding resolves into exactly one
class of the closed taxonomy. A symbol named by two clusters therefore carries
two classes, and the two dictate different remedies -- staged capability waits
for a dependency, should-be-live wants wiring -- so the ledger stops saying
what to do about it.

This is easy to introduce by accident and invisible to read: adding a symbol to
a cluster while an older cluster already names it produced seven such pairs in
a single edit, each looking correct in isolation. Two more predated that edit.
"""

from __future__ import annotations

import collections
import tomllib
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LEDGER: Final[Path] = REPO_ROOT / "dev" / "audit" / "reachability_classification.toml"


def _clusters() -> list[dict[str, object]]:
    """Return the classification clusters as recorded."""
    return list(tomllib.loads(_LEDGER.read_text(encoding="utf-8")).get("symbol_cluster", ()))


def _owner_names(clusters: list[dict[str, object]]) -> dict[str, list[str]]:
    """Return every symbol mapped to the clusters naming it."""
    owners: dict[str, list[str]] = collections.defaultdict(list)
    for cluster in clusters:
        symbols = cluster.get("symbols") or ()
        name = str(cluster.get("name", "<unnamed>"))
        for symbol in symbols:
            owners[str(symbol)].append(name)
    return owners


def test_the_ledger_carries_clusters() -> None:
    """An empty ledger would make the assertions below vacuous."""
    assert len(_clusters()) > 20


def test_no_symbol_is_claimed_by_two_clusters() -> None:
    """The direction the gate exists for: one finding, one class."""
    doubled = {symbol: owners for symbol, owners in _owner_names(_clusters()).items() if len(owners) > 1}
    assert not doubled, (
        "these symbols carry two classifications, so the ledger no longer says which "
        f"remedy applies; keep the more specific cluster and drop the other: {doubled}"
    )


def test_every_cluster_names_at_least_one_symbol() -> None:
    """A cluster naming nothing classifies nothing."""
    empty = [str(c.get("name", "<unnamed>")) for c in _clusters() if not (c.get("symbols") or ())]
    assert not empty, f"these clusters name no symbol: {empty}"


def test_every_cluster_carries_a_class_and_evidence() -> None:
    """Classification is evidenced, not asserted."""
    thin = [
        str(c.get("name", "<unnamed>"))
        for c in _clusters()
        if not c.get("class") or len(str(c.get("evidence", ""))) < 80
    ]
    assert not thin, f"these clusters lack a class or carry no substantive evidence: {thin}"


def test_the_gate_catches_a_planted_double_classification() -> None:
    """Detector teeth: the exact shape a careless addition produces."""
    planted = [
        {"name": "first", "symbols": ["SHARED", "ALPHA"]},
        {"name": "second", "symbols": ["SHARED"]},
    ]
    doubled = {s: o for s, o in _owner_names(planted).items() if len(o) > 1}
    assert doubled == {"SHARED": ["first", "second"]}
