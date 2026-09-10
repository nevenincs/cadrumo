"""Read the casilla lineage ledger's per-row refusals as lineage exceptions.

The ledger written by the lineage seeder is the one list of successor rows that
neither carry lineage nor declare their kind of none. Each ``[[refusal]]`` entry
names one row and classifies why it stops. Reading refuses a malformed entry or
a row named twice rather than letting either quietly widen the exception set.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cadrumo.domain.calculations.registry.casilla_lineage_totality import CasillaRowKey

from .casilla_lineage_seed import LEDGER_PATH

__all__ = ["LedgerRefusal", "load_ledger_refusals"]

_REQUIRED = ("modelo", "revision", "casilla", "category", "reason")


@dataclass(frozen=True, slots=True)
class LedgerRefusal:
    """One ledger entry: the row it excepts, and the classified reason it stops."""

    key: CasillaRowKey
    category: str
    reason: str


def load_ledger_refusals(path: Path = LEDGER_PATH) -> Mapping[CasillaRowKey, LedgerRefusal]:
    """Load every ``[[refusal]]`` keyed by the row it names."""
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    refusals: dict[CasillaRowKey, LedgerRefusal] = {}
    for index, entry in enumerate(document.get("refusal", ())):
        blank = [name for name in _REQUIRED if not isinstance(entry.get(name), str) or not entry[name].strip()]
        if blank:
            raise ValueError(f"{path.name}: refusal #{index} has no {', '.join(blank)}")
        key = CasillaRowKey(modelo=entry["modelo"], revision=entry["revision"], casilla=entry["casilla"])
        if key in refusals:
            raise ValueError(f"{path.name}: refusal #{index} names {key} a second time")
        refusals[key] = LedgerRefusal(key=key, category=entry["category"], reason=entry["reason"])
    return refusals
