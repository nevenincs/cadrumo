"""The frontend column of the persona table: the same returns driven through the TUI and the desktop window.

Each surface's pilot writes one JSON object per line into ``*.jsonl`` files of one directory (``read_results``
documents and enforces the schema). This module reads them, normalises a Python row's stages to the surface
vocabulary, and decides for each row whether a surface matched it, differs from it, could not be compared with it,
did not load the persona, or was not run. A match needs the same three stages and the same non-zero casilla
figures; a surface that shows less, more or other figures than the Python row differs.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from .rows import Stage, TableRow

SURFACES = ("tui", "window")
SURFACE_LABELS = {"tui": "TUI", "window": "window"}
NOT_REACHED = "not-reached"
STAGE_WORDS = ("pass", "incomplete", "refused", "not-owed", NOT_REACHED, "error")
"""The stage vocabulary of a surface result."""

STAGE_OF: Mapping[Stage, str | None] = {
    Stage.PASSED: "pass",
    Stage.CALCULATED: "pass",
    Stage.MISMATCH: "pass",
    Stage.UNRESOLVED: "pass",
    Stage.REFUSAL_NOT_RAISED: "pass",
    Stage.EXPECTED_REFUSAL: "refused",
    Stage.REFUSED: "refused",
    Stage.UNSUPPORTED: "refused",
    Stage.INCOMPLETE: "incomplete",
    Stage.OWED_SHOWN: "incomplete",
    Stage.NOT_OWED: "not-owed",
    Stage.NOT_REACHED: NOT_REACHED,
    Stage.HISTORY_FILED: None,
    Stage.NOT_RUN: None,
}
"""A Python stage in the surface vocabulary; ``None`` where no surface result can be compared with it.

A calculation that was produced counts as ``pass`` whatever the persona states about its values: the values are
compared through the figures.
"""

MATCHED, DIFFERS, NOT_COMPARABLE, LOAD_FAILED, NOT_RUN, EXTRA = (
    "matched",
    "differs",
    "not-comparable",
    "load-failed",
    "not-run",
    "extra",
)
CELL_WORDS = {
    MATCHED: "matched",
    DIFFERS: "differs",
    NOT_COMPARABLE: "not comparable",
    LOAD_FAILED: "load failed",
    NOT_RUN: "not run",
}

type RowKey = tuple[str, str, int, str]
type ResultKey = tuple[str, str, str | None, int | None, str | None]
"""``(surface, persona, modelo, year, period)``; a persona-level line has no modelo, year or period."""

_FIELDS = frozenset(
    {
        "surface",
        "tree",
        "persona",
        "modelo",
        "year",
        "period",
        "loads",
        "calculate",
        "verify",
        "export",
        "refusal_code",
        "figures",
        "reason",
        "log",
    }
)
_REQUIRED = frozenset({"surface", "tree", "persona", "modelo", "year", "period", "loads"})
_STAGE_FIELDS = ("calculate", "verify", "export")


class FrontendResultError(ValueError):
    """A surface result line the schema refuses; the message names the file and line."""


@dataclass(frozen=True, slots=True)
class SurfaceResult:
    """What one surface displayed for one return, or whether it loaded a persona's profile at all."""

    surface: str
    tree: str
    persona: str
    modelo: str | None
    year: int | None
    period: str | None
    loads: bool
    calculate: str = NOT_REACHED
    verify: str = NOT_REACHED
    export: str = NOT_REACHED
    refusal_code: str | None = None
    figures: tuple[tuple[str, str], ...] = ()
    reason: str = ""
    log: str = ""

    @property
    def key(self) -> ResultKey:
        """The result key ``(surface, persona, modelo, year, period)``."""
        return (self.surface, self.persona, self.modelo, self.year, self.period)


def read_results(directory: Path) -> dict[ResultKey, SurfaceResult]:
    """The latest result per key in the ``*.jsonl`` files of ``directory``, by file name and then line order.

    A line is a JSON object with ``surface`` (``tui`` or ``window``), ``tree`` (the commit the surface ran),
    ``persona``, ``modelo`` (null on a persona-level line, which reports whether the profile loaded), ``year``,
    ``period`` (null with a null ``modelo``), ``loads``, and, when ``modelo`` is set, ``calculate``, ``verify``
    and ``export`` in the stage vocabulary. ``refusal_code``, ``reason`` and ``log`` are optional text;
    ``figures`` is an optional object of every non-zero casilla value the surface displayed, as text.
    Unknown keys and bad values are refused.
    """
    if not directory.is_dir():
        raise FrontendResultError(f"frontend results directory {directory} does not exist")
    found: dict[ResultKey, SurfaceResult] = {}
    for path in sorted(directory.glob("*.jsonl")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                result = parse_result(line)
            except ValueError as error:
                raise FrontendResultError(f"{path}:{number}: {error}") from error
            found[result.key] = result
    return found


def parse_result(line: str) -> SurfaceResult:
    """One result line, refusing an unknown key, a missing required key or a value outside the schema."""
    try:
        document = json.loads(line)
    except ValueError as error:
        raise ValueError(f"not JSON: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("a result line must be a JSON object")
    data = cast("dict[str, object]", document)
    if unknown := sorted(set(data) - _FIELDS):
        raise ValueError(f"unknown key {', '.join(unknown)}")
    if missing := sorted(_REQUIRED - set(data)):
        raise ValueError(f"missing key {', '.join(missing)}")
    surface = _choice(data, "surface", SURFACES)
    modelo, year, period = _return_scope(data)
    stages = _stage_words(data, modelo)
    loads = data["loads"]
    if not isinstance(loads, bool):
        raise ValueError("loads must be true or false")
    return SurfaceResult(
        surface=surface,
        tree=_text(data, "tree"),
        persona=_text(data, "persona"),
        modelo=modelo,
        year=year,
        period=period,
        loads=loads,
        calculate=stages.get("calculate", NOT_REACHED),
        verify=stages.get("verify", NOT_REACHED),
        export=stages.get("export", NOT_REACHED),
        refusal_code=_optional_text(data, "refusal_code"),
        figures=_figures(data.get("figures", {})),
        reason=_optional_text(data, "reason") or "",
        log=_optional_text(data, "log") or "",
    )


def _return_scope(data: Mapping[str, object]) -> tuple[str | None, int | None, str | None]:
    """The ``(modelo, year, period)`` of a line: all set for a return, all null for a persona-level line."""
    modelo = _optional_text(data, "modelo")
    year, period = _optional_year(data), _optional_text(data, "period")
    if modelo is None and (year is not None or period is not None):
        raise ValueError("a persona-level line (modelo null) has no year or period")
    if modelo is not None and (year is None or period is None):
        raise ValueError("a line with a modelo needs a year and a period")
    return modelo, year, period


def _stage_words(data: Mapping[str, object], modelo: str | None) -> dict[str, str]:
    """The stage words a line states: all three for a return, any not null for a persona-level line."""
    if modelo is None:
        stated = {name: data[name] for name in _STAGE_FIELDS if data.get(name) is not None}
    else:
        _require_all_stages(data)
        stated = {name: data[name] for name in _STAGE_FIELDS}
    return {name: _choice(stated, name, STAGE_WORDS) for name in stated}


def _require_all_stages(data: Mapping[str, object]) -> None:
    absent = [name for name in _STAGE_FIELDS if name not in data]
    if absent:
        raise ValueError(f"missing key {', '.join(absent)}")


def _text(data: Mapping[str, object], name: str) -> str:
    value = data[name]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _optional_text(data: Mapping[str, object], name: str) -> str | None:
    value = data.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text or null")
    return value


def _optional_year(data: Mapping[str, object]) -> int | None:
    value = data["year"]
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("year must be an integer or null")
    return value


def _choice(data: Mapping[str, object], name: str, words: Iterable[str]) -> str:
    value = data[name]
    allowed = tuple(words)
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{name} must be one of {', '.join(allowed)}")
    return value


def _figures(raw: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, dict):
        raise ValueError("figures must be an object of casilla id to text")
    figures: dict[str, str] = {}
    for key, value in cast("dict[object, object]", raw).items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("figures must be an object of casilla id to text")
        figures[key] = value
    return tuple(sorted(figures.items()))


@dataclass(frozen=True, slots=True)
class RowParity:
    """How one surface's result stands against one Python row (or against no row, for an ``extra``)."""

    key: RowKey
    surface: str
    outcome: str
    causes: tuple[str, ...] = ()
    tree: str | None = None
    """The commit the surface ran, when a result was read for the row."""


@dataclass(frozen=True, slots=True)
class PersonaCell:
    """One persona on one surface: whether its profile loaded and how its table rows fared."""

    loads: bool | None
    """None when the surface has no line at all for the persona."""
    rows: int
    counts: Mapping[str, int]


def _number(text: str) -> Decimal | None:
    try:
        number = Decimal(text.strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _equal(table: str, shown: str) -> bool:
    """Whether two figure texts are equal: as numbers when both parse as one, else as text."""
    first, second = _number(table), _number(shown)
    return first == second if first is not None and second is not None else table == shown


def _is_zero(text: str) -> bool:
    number = _number(text)
    return number is not None and number == 0


def figure_causes(surface: str, table: Mapping[str, str], shown: Mapping[str, str]) -> list[str]:
    """Each way the figures ``shown`` by a surface disagree with the table row's ``table`` figures."""
    causes: list[str] = []
    for casilla in sorted(table):
        if casilla not in shown:
            causes.append(f"casilla {casilla} not shown")
        elif not _equal(table[casilla], shown[casilla]):
            causes.append(f"casilla {casilla} {surface} {shown[casilla]}, table {table[casilla]}")
    causes += [
        f"casilla {casilla} shown {shown[casilla]}, table has none"
        for casilla in sorted(set(shown) - set(table))
        if not _is_zero(shown[casilla])
    ]
    return causes


def parity(
    row: TableRow,
    surface: str,
    result: SurfaceResult | None,
    *,
    loads: bool | None = None,
    load_reason: str = "",
) -> RowParity:
    """How ``result`` of ``surface`` stands against ``row``; ``loads`` is False when the persona did not load there.

    ``load_reason`` is the reason that load failure gave. A missing result is ``not-run`` unless the load failed;
    a row with nothing to compare (history-filed, not run, or calculated with no recorded figures) is
    ``not-comparable`` and never matched.
    """
    tree = None if result is None else result.tree
    if loads is False or (result is not None and not result.loads):
        return RowParity(row.key, surface, LOAD_FAILED, (_load_failure_reason(result, load_reason),), tree)
    if result is None:
        return RowParity(row.key, surface, NOT_RUN)
    stages = {name: STAGE_OF[getattr(row, name)] for name in _STAGE_FIELDS}
    if (why := _uncomparable_reason(row, stages)) is not None:
        return RowParity(row.key, surface, NOT_COMPARABLE, (why,), tree)
    causes = _stage_causes(surface, stages, result)
    causes += figure_causes(surface, dict(row.figures), dict(result.figures))
    return RowParity(row.key, surface, DIFFERS if causes else MATCHED, tuple(causes), tree)


def _load_failure_reason(result: SurfaceResult | None, load_reason: str) -> str:
    """The reason a persona did not load: the one given, else the result's own, else a generic sentence."""
    reason = load_reason or (result.reason if result is not None else "")
    return reason or "the profile did not load"


def _uncomparable_reason(row: TableRow, stages: Mapping[str, str | None]) -> str | None:
    """Why the table row has nothing to compare a surface with, or ``None`` when it can be compared."""
    if empty := [name for name, word in stages.items() if word is None]:
        why = ", ".join(f"{name} {getattr(row, name).value}" for name in empty)
        return f"table row has no comparable stage: {why}"
    if stages["calculate"] == "pass" and not row.figures:
        return "table row calculated but records no figures"
    return None


def _stage_causes(surface: str, stages: Mapping[str, str | None], result: SurfaceResult) -> list[str]:
    """Each stage at which the surface's word differs from the table row's."""
    return [
        f"{name} {surface} {getattr(result, name)}, table {word}"
        for name, word in stages.items()
        if getattr(result, name) != word
    ]


@dataclass(frozen=True, slots=True)
class FrontendComparison:
    """Every surface's parity against the table's rows, and each persona's cell per surface."""

    rows: tuple[TableRow, ...]
    parities: Mapping[str, tuple[RowParity, ...]]
    """Per surface: one parity per table row, in key order."""
    extras: Mapping[str, tuple[RowParity, ...]]
    """Per surface: the results the table has no row for."""
    cells: Mapping[tuple[str, str], PersonaCell]
    """Per ``(persona, surface)``."""

    def personas(self) -> list[str]:
        """The personas of the table's rows and of the results, sorted."""
        return sorted({persona for persona, _ in self.cells})

    def matched(self, surface: str) -> int:
        """The table rows ``surface`` matched."""
        return sum(item.outcome == MATCHED for item in self.parities[surface])


def compare_frontend(rows: Iterable[TableRow], results: Mapping[ResultKey, SurfaceResult]) -> FrontendComparison:
    """Compare ``results`` with the table's ``rows`` on every surface."""
    ordered = tuple(sorted(rows, key=lambda row: row.key))
    keys = {row.key for row in ordered}
    personas = sorted({row.persona for row in ordered} | {result.persona for result in results.values()})
    parities: dict[str, tuple[RowParity, ...]] = {}
    extras: dict[str, tuple[RowParity, ...]] = {}
    cells: dict[tuple[str, str], PersonaCell] = {}
    for surface in SURFACES:
        held = {key: result for key, result in results.items() if key[0] == surface}
        loads = {persona: _loads(held, persona) for persona in personas}
        found = _surface_parities(ordered, surface, held, loads)
        parities[surface] = found
        extras[surface] = _surface_extras(surface, held, keys)
        for persona in personas:
            cells[persona, surface] = _persona_cell(found, persona, loads[persona])
    return FrontendComparison(ordered, parities, extras, cells)


def _surface_parities(
    ordered: Iterable[TableRow],
    surface: str,
    held: Mapping[ResultKey, SurfaceResult],
    loads: Mapping[str, bool | None],
) -> tuple[RowParity, ...]:
    """One parity per table row for ``surface``, given the results it ``held`` and each persona's load state."""
    return tuple(
        parity(
            row,
            surface,
            held.get((surface, row.persona, row.modelo, row.year, row.period)),
            loads=loads[row.persona],
            load_reason=_load_reason(held, row.persona),
        )
        for row in ordered
    )


def _surface_extras(surface: str, held: Mapping[ResultKey, SurfaceResult], keys: set[RowKey]) -> tuple[RowParity, ...]:
    """The return results of ``surface`` that no table row (``keys``) accounts for."""
    extras: list[RowParity] = []
    for _, result in sorted(held.items(), key=lambda item: str(item[0])):
        if result.modelo is None or result.year is None or result.period is None:
            continue
        key = (result.persona, result.modelo, result.year, result.period)
        if key not in keys:
            extras.append(RowParity(key, surface, EXTRA, ("no table row",), result.tree))
    return tuple(extras)


def _persona_cell(found: Iterable[RowParity], persona: str, loads: bool | None) -> PersonaCell:
    """``persona``'s cell on one surface from the parities of that surface's rows."""
    mine = [item for item in found if item.key[0] == persona]
    return PersonaCell(loads, len(mine), Counter(item.outcome for item in mine))


def _persona_line(held: Mapping[ResultKey, SurfaceResult], persona: str) -> SurfaceResult | None:
    return next((result for key, result in held.items() if key[1] == persona and key[2] is None), None)


def _loads(held: Mapping[ResultKey, SurfaceResult], persona: str) -> bool | None:
    """Whether the persona's profile loaded on a surface: its own line, else any line's, else not yet run."""
    line = _persona_line(held, persona)
    if line is not None:
        return line.loads
    mine = [result for key, result in held.items() if key[1] == persona]
    if not mine:
        return None
    return all(result.loads for result in mine)


def _load_reason(held: Mapping[ResultKey, SurfaceResult], persona: str) -> str:
    line = _persona_line(held, persona)
    if line is not None and not line.loads:
        return line.reason
    return ""


def cell_text(cell: PersonaCell) -> str:
    """The persona cell summary, ``loads, 5/7 matched, 1 differs, 1 not run``, or ``not yet run``.

    Rows that could not be compared and rows lost to a failed load are named after the three counts when there are any.
    """
    if cell.loads is None:
        return "not yet run"
    counts = cell.counts
    parts = [
        "loads" if cell.loads else "does not load",
        f"{counts.get(MATCHED, 0)}/{cell.rows} matched",
        f"{counts.get(DIFFERS, 0)} differs",
        f"{counts.get(NOT_RUN, 0)} not run",
    ]
    if counts.get(NOT_COMPARABLE, 0):
        parts.append(f"{counts.get(NOT_COMPARABLE, 0)} not comparable")
    if counts.get(LOAD_FAILED, 0):
        parts.append(f"{counts.get(LOAD_FAILED, 0)} load failed")
    return ", ".join(parts)


def row_cell(item: RowParity, head: str) -> str:
    """The main table's cell for one row on one surface; the tree is named when it is not ``head``."""
    text = CELL_WORDS[item.outcome]
    return f"{text} @{item.tree}" if item.tree is not None and item.tree != head else text


def frontend_line(comparison: FrontendComparison) -> str:
    """The summary sentence, ``Frontend: TUI matched a / N, window matched b / N (N rows)``."""
    total = len(comparison.rows)
    matched = ", ".join(
        f"{SURFACE_LABELS[surface]} matched {comparison.matched(surface)} / {total}" for surface in SURFACES
    )
    return f"Frontend: {matched} ({total} rows)"


__all__ = [
    "CELL_WORDS",
    "STAGE_OF",
    "STAGE_WORDS",
    "SURFACES",
    "SURFACE_LABELS",
    "FrontendComparison",
    "FrontendResultError",
    "PersonaCell",
    "RowParity",
    "SurfaceResult",
    "cell_text",
    "compare_frontend",
    "figure_causes",
    "frontend_line",
    "parity",
    "parse_result",
    "read_results",
    "row_cell",
]
