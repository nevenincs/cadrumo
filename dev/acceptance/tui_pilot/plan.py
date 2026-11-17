"""Which returns the TUI pilot drives for a persona, in which replay and order, and what the table expects of each.

Nothing is planned here: the returns reported are the persona's rows of the persona table's rows file
(:data:`TABLE_ROWS_ENV`), each at the replay horizon the table reports it at, and each replay runs the returns the
table's own planner (``persona_table.rows.owed_rows``) owes there, in its chain order, up to the last one reported.
A return the table reports at several horizons is a row of each, with its own figures, driven by the replay at each.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_world import year_envelope
from cadrumo.tests.persona_types import YearEnvelope

from ..persona_table.rows import PlannedRow, TableRow, owed_rows, read_rows
from ..persona_table.unchecked import persona_at

TABLE_ROWS_ENV: Final = "TUI_PILOT_TABLE_ROWS"
"""The persona table's rows file (``rows-<tree>.jsonl``) whose rows the pilot reports and compares with."""

type RowKey = tuple[str, str, int, str]
type ExpectedKey = tuple[RowKey, int]
"""A table row's return key and the horizon the table replayed it at."""


class TableRowsUnavailableError(RuntimeError):
    """The environment names no readable persona table rows file."""


@dataclass(frozen=True, slots=True)
class PilotReplay:
    """One horizon the persona is replayed at, the returns it runs there in chain order, and those it reports."""

    horizon: int
    returns: tuple[PlannedRow, ...]
    reported: frozenset[RowKey]


@dataclass(frozen=True, slots=True)
class PilotPlan:
    """Every replay of one persona, the table row of each reported return, and those no replay owes."""

    replays: tuple[PilotReplay, ...]
    expected: dict[ExpectedKey, TableRow]
    unplanned: tuple[TableRow, ...]
    """Table rows the planner does not owe at the table row's horizon; the pilot cannot drive them."""


@cache
def pilot_envelope() -> YearEnvelope:
    """The registry's supported filing-year envelope, as the persona table reads it."""
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def table_rows_path() -> Path:
    """The rows file :data:`TABLE_ROWS_ENV` names."""
    named = os.environ.get(TABLE_ROWS_ENV, "")
    if not named:
        raise TableRowsUnavailableError(f"{TABLE_ROWS_ENV} names no persona table rows file")
    path = Path(named)
    if not path.is_file():
        raise TableRowsUnavailableError(f"{TABLE_ROWS_ENV} names {path}, which is not a file")
    return path


@cache
def _table(path: Path) -> dict[ExpectedKey, TableRow]:
    """The latest row per return and horizon; a later row of the same horizon replaces an earlier one."""
    return {(row.key, row.horizon): row for row in read_rows([path])}


def expected_rows(persona_id: str, path: Path) -> dict[ExpectedKey, TableRow]:
    """The persona's latest table row per return and horizon in the rows file at ``path``."""
    return {key: row for key, row in _table(path).items() if row.persona == persona_id}


def pilot_plan(persona_id: str, path: Path, envelope: YearEnvelope) -> PilotPlan:
    """The replays that drive every return the table reports for the persona, newest horizon first."""
    return plan_replays(
        expected_rows(persona_id, path),
        lambda horizon: owed_rows(persona_at(persona_id, horizon, envelope), horizon, envelope),
    )


def plan_replays(expected: dict[ExpectedKey, TableRow], owed: Callable[[int], Sequence[PlannedRow]]) -> PilotPlan:
    """The replays that drive every row of ``expected``, newest horizon first; ``owed`` is the planner at a horizon."""
    replays: list[PilotReplay] = []
    unplanned: list[TableRow] = []
    for horizon in sorted({held for _, held in expected}, reverse=True):
        wanted = {key for key, held in expected if held == horizon}
        planned = owed(horizon)
        keys = [row.key for row in planned]
        unplanned += [expected[key, horizon] for key in sorted(wanted - set(keys))]
        reported = frozenset(wanted & set(keys))
        if not reported:
            continue
        last = max(index for index, key in enumerate(keys) if key in reported)
        replays.append(PilotReplay(horizon=horizon, returns=tuple(planned[: last + 1]), reported=reported))
    return PilotPlan(replays=tuple(replays), expected=expected, unplanned=tuple(unplanned))
