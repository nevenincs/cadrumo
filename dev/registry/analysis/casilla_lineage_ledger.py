"""Read the casilla lineage ledger's per-row refusals as lineage exceptions.

The ledger written by the lineage seeder is the one list of successor rows that
neither carry lineage nor declare their kind of none. Each ``[[refusal]]`` entry
names one row and classifies why it stops. Reading refuses a malformed entry or
a row named twice rather than letting either quietly widen the exception set.

An entry is either *freshly judged* -- the run that wrote the ledger loaded its
modelo and judged the row -- or *carried forward*: the run could not load or
could not plan that modelo, so it copied the row's previous entry verbatim
rather than dropping it and shrinking the ledger. A carried entry states so in
``carried_from_previous_run``, names in ``carried_reason`` why the row could not
be rejudged, and records in ``last_judged`` the run identifier of the last run
that actually judged it, with ``carried_runs`` counting how many consecutive
runs have carried it since. A carried entry that names no ``last_judged`` is
refused: an assertion about a corpus state, with no statement of which corpus
state, is the one shape that could lie without being detectable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.casilla_lineage_totality import CasillaRowKey

from .casilla_lineage_seed import LEDGER_PATH

__all__ = ["LedgerRefusal", "load_ledger_refusals"]

_REQUIRED = ("modelo", "revision", "casilla", "category", "reason")


class _CarriageKwargs(TypedDict, total=False):
    """Validated optional carriage fields passed to :class:`LedgerRefusal`."""

    carried_from_previous_run: bool
    carried_reason: str
    last_judged: str
    carried_runs: int


@dataclass(frozen=True, slots=True)
class LedgerRefusal:
    """One ledger entry: the row it excepts, the classified reason it stops, and when it was judged.

    ``last_judged`` is the identifier of the run that actually judged the row.
    It is ``None`` on a freshly judged entry, which the ledger's own ``[run]``
    table dates, and a run identifier on a carried entry, which the current run
    did not judge at all.
    """

    key: CasillaRowKey
    category: str
    reason: str
    carried_from_previous_run: bool = False
    carried_reason: str | None = None
    last_judged: str | None = None
    carried_runs: int = 0


def load_ledger_refusals(path: Path = LEDGER_PATH) -> Mapping[CasillaRowKey, LedgerRefusal]:
    """Load every ``[[refusal]]`` keyed by the row it names."""
    document = parse_toml(path.read_text(encoding="utf-8"))
    refusals: dict[CasillaRowKey, LedgerRefusal] = {}
    for index, entry in enumerate(document.get("refusal", ())):
        blank = [name for name in _REQUIRED if not isinstance(entry.get(name), str) or not entry[name].strip()]
        if blank:
            raise ValueError(f"{path.name}: refusal #{index} has no {', '.join(blank)}")
        key = CasillaRowKey(modelo=entry["modelo"], revision=entry["revision"], casilla=entry["casilla"])
        if key in refusals:
            raise ValueError(f"{path.name}: refusal #{index} names {key} a second time")
        refusals[key] = LedgerRefusal(
            key=key,
            category=entry["category"],
            reason=entry["reason"],
            **_carriage(path, index, entry),
        )
    return refusals


def _carriage(path: Path, index: int, entry: Mapping[str, object]) -> _CarriageKwargs:
    """The carriage fields of one entry, refusing a carried entry that dates nothing."""
    carried = entry.get("carried_from_previous_run", False)
    if not isinstance(carried, bool):
        raise ValueError(f"{path.name}: refusal #{index} has a non-boolean carried_from_previous_run")
    if not carried:
        return {"carried_from_previous_run": False}
    last_judged = entry.get("last_judged")
    if not isinstance(last_judged, str) or not last_judged.strip():
        raise ValueError(f"{path.name}: carried refusal #{index} has no last_judged")
    reason = entry.get("carried_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(f"{path.name}: carried refusal #{index} has no carried_reason")
    runs = entry.get("carried_runs")
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
        raise ValueError(f"{path.name}: carried refusal #{index} has no positive carried_runs")
    return {
        "carried_from_previous_run": True,
        "carried_reason": reason,
        "last_judged": last_judged,
        "carried_runs": runs,
    }
