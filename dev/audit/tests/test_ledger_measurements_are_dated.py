"""Gate: a recorded count in the ledger must say when it was true.

The classification ledger mixes two kinds of statement. A cluster's evidence is
an argument about a symbol, and it stays true until the symbol changes. A
measurement -- ``exact_total``, ``declared_exports``, ``population`` -- is a
photograph of a moving tree, and it starts decaying the moment it is written.

Three of them had no date. ``exported_unused`` recorded 8534 declared exports
and 368 unconsumed, and the prose beneath derived "4.3% of the declared
surface" from that pair; two days and one deletion sweep later the live figures
were near 8061 and 310, so the sentence stated a proportion that no longer
held, with nothing on the page to warn a reader. The numbers were not wrong
when taken. They were wrong to present undated.

This does not require a measurement to be CURRENT -- forcing that would make
every deletion red this gate and turn a considered analysis into churn. It
requires only that it be dated, so a reader can weigh it. The distinction is
the point: a dated snapshot is evidence, an undated one is a claim about now.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LEDGER: Final[Path] = REPO_ROOT / "dev" / "audit" / "reachability_classification.toml"

#: Tables holding adjudications rather than measurements. Their integers are
#: properties of a named symbol, not a count of a population that moves.
_ADJUDICATION_TABLES: Final[frozenset[str]] = frozenset(
    {"symbol_cluster", "module", "test_module", "intentional"}
)


def undated_measurement_tables(data: dict[str, Any]) -> list[str]:
    """Return top-level tables that record an integer count and no ``measured``."""
    undated: list[str] = []
    for name, value in sorted(data.items()):
        if name in _ADJUDICATION_TABLES or not isinstance(value, dict):
            continue
        counts = [k for k, v in value.items() if isinstance(v, int) and not isinstance(v, bool)]
        if counts and "measured" not in value:
            undated.append(f"{name} (records {', '.join(sorted(counts))})")
    return undated


def test_the_ledger_still_holds_measurement_tables() -> None:
    """A population floor: no measurement tables would make the check vacuous."""
    data = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    measured = [
        name
        for name, value in data.items()
        if name not in _ADJUDICATION_TABLES
        and isinstance(value, dict)
        and any(isinstance(v, int) and not isinstance(v, bool) for v in value.values())
    ]

    assert len(measured) >= 3, (
        f"only {len(measured)} measurement table(s) found ({sorted(measured)}); the "
        "ledger shape has moved and this gate is inert rather than satisfied"
    )


def test_every_recorded_measurement_carries_its_date() -> None:
    """The direction the gate exists for."""
    undated = undated_measurement_tables(tomllib.loads(_LEDGER.read_text(encoding="utf-8")))

    assert undated == [], (
        "these ledger tables record a count with no `measured` date, so a stale "
        f"figure reads as a current one: {undated}"
    )


def test_the_gate_catches_an_undated_count() -> None:
    """Detector teeth: the exact shape three tables carried."""
    assert undated_measurement_tables({"exported_unused": {"declared_exports": 8534}}) == [
        "exported_unused (records declared_exports)"
    ]


def test_a_dated_count_is_accepted() -> None:
    """The normal case, so the gate is not merely always-red."""
    assert undated_measurement_tables({"exported_unused": {"measured": "2026-09-04", "declared_exports": 8534}}) == []


def test_an_adjudication_table_needs_no_date() -> None:
    """A cluster's counts describe a named symbol, not a moving population."""
    data = {"symbol_cluster": {"names": 5}, "module": {"subjects": 2}}

    assert undated_measurement_tables(data) == []


def test_a_table_carrying_no_count_needs_no_date() -> None:
    """Prose-only tables make no measurement to go stale."""
    assert undated_measurement_tables({"notes": {"method": "a name counts as consumed only when..."}}) == []
