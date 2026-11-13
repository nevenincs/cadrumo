"""The frontend column of the persona table: the same returns driven through the TUI, the desktop window and the CLI.

Each surface's pilot writes one JSON object per line into ``*.jsonl`` files of one directory (``read_results``
documents and enforces the schema). This module reads them, normalises a Python row's stages to the surface
vocabulary, and decides for each row whether a surface matched it, differs from it, could not be compared with it,
did not load the persona, or was not run. The table row is the oracle for calculated values: a match needs the
same three stages and every casilla figure of the table row shown with an equal value. A casilla the surface shows
that the row has no figure for (identity fields, rates, period) never makes a row differ; the rows that show such
casillas are counted and the names stay on the parity.

Export unavailable is one outcome, whether the backend refuses an attempt or the form does not serve the export
door. The export stage matches a surface's ``not-reached`` against the table's ``refused`` only when both hold: the
line states ``export_served`` false (the form served no export door for that return, recorded as served state and not
as the pilot's choice) and the table's export refusal code is one of ``EXPORT_WITHHELD_UNVERIFIED`` (the codes the
export operation raises for a revision that is not sealed, read from the table row's reason by
``export_refusal_code``). The comparison is recorded in ``RowParity.gated_stages`` as ``export unavailable
(refused | not served)`` followed by the code, the persona cell counts the rows as ``N rows matched by gating`` and
the report lists them. Every other stage difference stays a difference, and the rule reads stage words and that
code only. The file stage is not compared with the table, so the rule has no file case.

A persona-level line (``modelo`` null) may state the integer ``horizon`` it was run at; producers that write one
persona line per horizon use it so a load failure at one horizon fails only the table rows of that horizon. When the
field is absent or null the horizon is read from the start of ``reason`` (``horizon <year>`` or ``<persona>@<year>``);
if neither matches the line has no horizon and speaks for every row of the persona that no horizon line answers for.
A table row that has a result line of its own on a surface is judged by that line and never load-failed by a persona
line.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from .rows import Stage, TableRow

SURFACES = ("tui", "window", "cli")
SURFACE_LABELS = {"tui": "TUI", "window": "window", "cli": "CLI"}
NOT_REACHED = "not-reached"
STAGE_WORDS = ("pass", "incomplete", "refused", "not-owed", NOT_REACHED, "error")
"""The stage vocabulary of a surface result."""

EXPORT_WITHHELD_UNVERIFIED = ("REFUSED_MODELO_REVISION_NOT_SEALED",)
"""The codes the export operation raises for a revision that is not sealed (unverified, so no grant sealed it)."""
EXPORT_UNAVAILABLE = "export unavailable (refused | not served)"
"""How the comparison of a not-served export door with the table's withheld export is recorded."""
_EXPORT_CODE = re.compile(r"\bexport:.*?\b((?:REFUSED|ERROR)_[A-Z0-9_]+)")
_HORIZON_PREFIX = re.compile(r"horizon (\d{4})\b")

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
"""``(surface, persona, modelo, year, period)``.

A persona-level line has no modelo, year or period; its year slot holds its horizon (``None`` without one)."""

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
        "export_served",
        "file",
        "refusal_code",
        "figures",
        "reason",
        "log",
        "horizon",
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
    export_served: bool | None = None
    """Whether the form served an export door for the return; ``None`` when the line does not state it."""
    file: str | None = None
    """The file stage in the stage vocabulary; ``None`` when the line does not state it. Not compared with the table."""
    refusal_code: str | None = None
    figures: tuple[tuple[str, str], ...] = ()
    reason: str = ""
    log: str = ""
    horizon: int | None = None
    """The horizon a persona-level line was run at, stated or read from its reason; ``None`` on a return line."""

    @property
    def key(self) -> ResultKey:
        """The result key ``(surface, persona, modelo, year, period)``; a persona line holds its horizon as year."""
        return (
            self.surface,
            self.persona,
            self.modelo,
            self.horizon if self.modelo is None else self.year,
            self.period,
        )


def read_results(directory: Path) -> dict[ResultKey, SurfaceResult]:
    """The latest result per key in the ``*.jsonl`` files of ``directory``.

    Files are read oldest first (by modification time, then name), each in line order.

    A line is a JSON object with ``surface`` (``tui``, ``window`` or ``cli``), ``tree`` (the commit the surface ran),
    ``persona``, ``modelo`` (null on a persona-level line, which reports whether the profile loaded), ``year``,
    ``period`` (null with a null ``modelo``), ``loads``, and, when ``modelo`` is set, ``calculate``, ``verify``
    and ``export`` in the stage vocabulary; the optional ``file`` states a fifth stage in the same vocabulary (absent
    means not stated; the table row has no file stage yet, so parity ignores it). The optional ``export_served`` is
    true or false: false states the form served no export door for the return (served state, never the pilot's choice);
    absent means unknown. ``refusal_code``, ``reason`` and
    ``log`` are optional text;
    ``figures`` is an optional object of every non-zero casilla value the surface displayed, as text; the table
    row is compared on the casillas of its form only, never on its internal figures.
    The optional ``horizon`` (an integer or null, persona-level lines only) names the horizon a persona line was run
    at; absent, it is read from the reason's ``horizon <year>`` or ``<persona>@<year>`` prefix.
    Unknown keys and bad values are refused.
    """
    if not directory.is_dir():
        raise FrontendResultError(f"frontend results directory {directory} does not exist")
    found: dict[ResultKey, SurfaceResult] = {}
    for path in sorted(directory.glob("*.jsonl"), key=lambda path: (path.stat().st_mtime_ns, path.name)):
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
    persona = _text(data, "persona")
    reason = _optional_text(data, "reason") or ""
    return SurfaceResult(
        surface=surface,
        tree=_text(data, "tree"),
        persona=persona,
        modelo=modelo,
        year=year,
        period=period,
        loads=loads,
        calculate=stages.get("calculate", NOT_REACHED),
        verify=stages.get("verify", NOT_REACHED),
        export=stages.get("export", NOT_REACHED),
        export_served=_optional_bool(data, "export_served"),
        file=_optional_stage(data, "file"),
        refusal_code=_optional_text(data, "refusal_code"),
        figures=_figures(data.get("figures", {})),
        reason=reason,
        log=_optional_text(data, "log") or "",
        horizon=_line_horizon(data, persona, modelo, reason),
    )


def _line_horizon(data: Mapping[str, object], persona: str, modelo: str | None, reason: str) -> int | None:
    """The horizon of a persona-level line: the stated one, else the one its reason starts with, else ``None``."""
    value = data.get("horizon")
    if modelo is not None:
        if value is not None:
            raise ValueError("a line with a modelo has no horizon")
        return None
    if value is not None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("horizon must be an integer or null")
        return value
    match = _HORIZON_PREFIX.match(reason) or re.match(rf"{re.escape(persona)}@(\d{{4}})\b", reason)
    return None if match is None else int(match.group(1))


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


def _optional_stage(data: Mapping[str, object], name: str) -> str | None:
    """The stage word of an optional stage field, ``None`` when absent or null."""
    return None if data.get(name) is None else _choice(data, name, STAGE_WORDS)


def _optional_bool(data: Mapping[str, object], name: str) -> bool | None:
    value = data.get(name)
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"{name} must be true, false or null")
    return value


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
    extra_names: tuple[str, ...] = ()
    """The non-zero casillas the surface showed that the table row has no figure for; never a cause of a difference."""
    gated_stages: tuple[str, ...] = ()
    """``export unavailable (refused | not served)`` and the table's refusal code, when the export stage matched so."""

    @property
    def extra_casillas(self) -> int:
        """How many casillas the surface showed beyond the table row's figures."""
        return len(self.extra_names)


@dataclass(frozen=True, slots=True)
class PersonaCell:
    """One persona on one surface: whether its profile loaded and how its table rows fared."""

    loads: bool | None
    """None when the surface has no line at all for the persona."""
    rows: int
    counts: Mapping[str, int]
    extra_rows: int = 0
    """The rows on which the surface showed casillas the table row has no figure for."""
    trees: tuple[str, ...] = ()
    """The trees of the results the cell summarises (rows and the persona's own line), sorted and distinct."""
    gated_rows: int = 0
    """The rows with a stage that matched by gating."""


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
    """Each way the figures ``shown`` by a surface miss or disagree with the table row's ``table`` figures.

    The table row is the oracle for calculated values, so a casilla shown beyond ``table`` is not a cause.
    ``table`` holds only the casillas the revision's form places; the row's internal figures (working figures and
    unplaced casillas, which no surface is held to show) are never compared and are not extras when shown.
    """
    causes: list[str] = []
    for casilla in sorted(table):
        if casilla not in shown:
            causes.append(f"casilla {casilla} not shown")
        elif not _equal(table[casilla], shown[casilla]):
            causes.append(f"casilla {casilla} {surface} {shown[casilla]}, table {table[casilla]}")
    return causes


def extra_figures(table: Mapping[str, str], shown: Mapping[str, str]) -> tuple[str, ...]:
    """The non-zero casillas ``shown`` that the table row has no figure for, sorted."""
    return tuple(casilla for casilla in sorted(set(shown) - set(table)) if not _is_zero(shown[casilla]))


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
    a row with nothing to compare (history-filed, not run, or calculated in a file written before figures
    were recorded) is ``not-comparable`` and never matched. A row that recorded no non-zero figure compares on its
    stages, and the figure test passes with no table figure to find.
    """
    tree = None if result is None else result.tree
    if loads is False or (result is not None and not result.loads):
        return RowParity(row.key, surface, LOAD_FAILED, (_load_failure_reason(result, load_reason),), tree)
    if result is None:
        return RowParity(row.key, surface, NOT_RUN)
    stages = {name: STAGE_OF[getattr(row, name)] for name in _STAGE_FIELDS}
    if (why := _uncomparable_reason(row, stages)) is not None:
        return RowParity(row.key, surface, NOT_COMPARABLE, (why,), tree)
    table, shown = dict(row.figures), dict(result.figures)
    stage_causes, gated = _stage_causes(surface, stages, result, export_refusal_code(row.reason))
    causes = stage_causes + figure_causes(surface, table, shown)
    outcome = DIFFERS if causes else MATCHED
    extras = extra_figures(table | dict(row.internal_figures), shown)
    return RowParity(row.key, surface, outcome, tuple(causes), tree, extras, gated)


def _load_failure_reason(result: SurfaceResult | None, load_reason: str) -> str:
    """The reason a persona did not load: the one given, else the result's own, else a generic sentence."""
    reason = load_reason or (result.reason if result is not None else "")
    return reason or "the profile did not load"


def _uncomparable_reason(row: TableRow, stages: Mapping[str, str | None]) -> str | None:
    """Why the table row has nothing to compare a surface with, or ``None`` when it can be compared."""
    if empty := [name for name, word in stages.items() if word is None]:
        why = ", ".join(f"{name} {getattr(row, name).value}" for name in empty)
        return f"table row has no comparable stage: {why}"
    if stages["calculate"] == "pass" and not row.figures_recorded:
        return "table row calculated but records no figures"
    return None


def export_refusal_code(reason: str) -> str | None:
    """The first ``REFUSED_``/``ERROR_`` code after ``export:`` in a table row's reason; ``None`` when none."""
    if (match := _EXPORT_CODE.search(reason)) is None:
        return None
    return str(match.group(1))


def _export_unavailable(name: str, word: str | None, result: SurfaceResult, code: str | None) -> bool:
    """Whether the surface's ``not-reached`` export is the table's refusal for an unsealed revision.

    It is, only when the form served no export door (``export_served`` false, never absent) and the table's export
    refusal code is one of ``EXPORT_WITHHELD_UNVERIFIED``.
    """
    return (
        name == "export"
        and result.export == NOT_REACHED
        and result.export_served is False
        and word == "refused"
        and code in EXPORT_WITHHELD_UNVERIFIED
    )


def _stage_causes(
    surface: str, stages: Mapping[str, str | None], result: SurfaceResult, code: str | None
) -> tuple[list[str], tuple[str, ...]]:
    """Each stage at which the surface's word differs from the table row's, and the stages matched as unavailable."""
    causes: list[str] = []
    gated: list[str] = []
    for name, word in stages.items():
        if getattr(result, name) == word:
            continue
        if _export_unavailable(name, word, result, code):
            gated.append(f"{EXPORT_UNAVAILABLE} {code}")
        else:
            causes.append(f"{name} {surface} {getattr(result, name)}, table {word}")
    return causes, tuple(gated)


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

    def trees_folded(self, surface: str) -> Counter[str]:
        """Per tree, the table rows whose result on ``surface`` came from it."""
        return Counter(item.tree for item in self.parities[surface] if item.tree is not None)


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
        lines = {persona: _persona_lines(held, persona) for persona in personas}
        found = _surface_parities(ordered, surface, held, lines)
        parities[surface] = found
        extras[surface] = _surface_extras(surface, held, keys)
        for persona in personas:
            cells[persona, surface] = _persona_cell(found, persona, lines[persona], _results_load(held, persona))
    return FrontendComparison(ordered, parities, extras, cells)


def _surface_parities(
    ordered: Iterable[TableRow],
    surface: str,
    held: Mapping[ResultKey, SurfaceResult],
    lines: Mapping[str, Mapping[int | None, SurfaceResult]],
) -> tuple[RowParity, ...]:
    """One parity per table row for ``surface``, given the results it ``held`` and each persona's own lines."""
    found: list[RowParity] = []
    for row in ordered:
        result = held.get((surface, row.persona, row.modelo, row.year, row.period))
        loads, reason = (None, "") if result is not None else _row_load(lines[row.persona], held, row)
        found.append(parity(row, surface, result, loads=loads, load_reason=reason))
    return tuple(found)


def _row_load(
    lines: Mapping[int | None, SurfaceResult], held: Mapping[ResultKey, SurfaceResult], row: TableRow
) -> tuple[bool | None, str]:
    """Whether the persona loaded for a row that has no result line, and the reason when it did not.

    The persona line of the row's horizon speaks for it, else the horizon-less persona line; with no persona line at
    all the return lines of the persona do, and a persona with only other horizons' lines loaded by default.
    """
    if not lines:
        return _results_load(held, row.persona), ""
    line = lines.get(row.horizon, lines.get(None))
    if line is None or line.loads:
        return None, ""
    return False, line.reason


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


def _persona_cell(
    found: Iterable[RowParity],
    persona: str,
    lines: Mapping[int | None, SurfaceResult],
    results_load: bool | None,
) -> PersonaCell:
    """``persona``'s cell on one surface from the parities of that surface's rows and its own lines' trees.

    The persona does not load only when every one of its table rows failed to load; without rows the cell follows
    its lines (none loaded), else the return lines.
    """
    mine = [item for item in found if item.key[0] == persona]
    counts = Counter(item.outcome for item in mine)
    trees = {item.tree for item in mine if item.tree is not None} | {line.tree for line in lines.values()}
    return PersonaCell(
        _cell_loads(counts, len(mine), lines, results_load),
        len(mine),
        counts,
        sum(item.extra_casillas > 0 for item in mine),
        tuple(sorted(trees)),
        sum(bool(item.gated_stages) for item in mine),
    )


def _cell_loads(
    counts: Mapping[str, int], rows: int, lines: Mapping[int | None, SurfaceResult], results_load: bool | None
) -> bool | None:
    """The cell's load state: ``None`` when nothing was read for the persona, ``False`` only when no row loaded."""
    if not lines and results_load is None:
        return None
    if rows:
        return counts.get(LOAD_FAILED, 0) < rows
    return any(line.loads for line in lines.values()) if lines else results_load


def _persona_lines(held: Mapping[ResultKey, SurfaceResult], persona: str) -> dict[int | None, SurfaceResult]:
    """The persona-level lines of ``persona`` by horizon (``None`` for a line without one), the latest of each."""
    return {key[3]: result for key, result in held.items() if key[1] == persona and key[2] is None}


def _results_load(held: Mapping[ResultKey, SurfaceResult], persona: str) -> bool | None:
    """Whether the persona's lines all loaded; ``None`` when the surface has no line of the persona."""
    mine = [result for key, result in held.items() if key[1] == persona]
    return all(result.loads for result in mine) if mine else None


def cell_text(cell: PersonaCell, head: str | None = None) -> str:
    """The persona cell summary, ``loads, 5/7 matched, 1 differs, 1 not run``, or ``not yet run``.

    Rows that could not be compared, rows lost to a failed load, rows that show extra casillas and rows with a stage
    matched by gating are named after the three counts when there are any. With ``head`` given, the sorted trees of
    the cell's results that are not ``head`` close it as `` @<tree>,<tree>``.
    """
    if cell.loads is None:
        return "not yet run"
    others = [tree for tree in cell.trees if head is not None and tree != head]
    return ", ".join(_cell_parts(cell)) + (f" @{','.join(others)}" if others else "")


def _cell_parts(cell: PersonaCell) -> list[str]:
    """The comma-separated parts of a persona cell that has a surface line."""
    counts = cell.counts
    parts = [
        "loads" if cell.loads is True else "does not load",
        f"{counts.get(MATCHED, 0)}/{cell.rows} matched",
        f"{counts.get(DIFFERS, 0)} differs",
        f"{counts.get(NOT_RUN, 0)} not run",
    ]
    if counts.get(NOT_COMPARABLE, 0):
        parts.append(f"{counts.get(NOT_COMPARABLE, 0)} not comparable")
    if counts.get(LOAD_FAILED, 0):
        parts.append(f"{counts.get(LOAD_FAILED, 0)} load failed")
    if cell.extra_rows:
        parts.append(f"{cell.extra_rows} rows show extra casillas")
    if cell.gated_rows:
        parts.append(f"{cell.gated_rows} rows matched by gating")
    return parts


def row_cell(item: RowParity, head: str) -> str:
    """The main table's cell for one row on one surface; the tree is named when it is not ``head``."""
    text = CELL_WORDS[item.outcome]
    return f"{text} @{item.tree}" if item.tree is not None and item.tree != head else text


def frontend_line(comparison: FrontendComparison) -> str:
    """The summary sentence, ``Frontend: TUI matched a / N, window matched b / N, CLI matched c / N (N rows)``."""
    total = len(comparison.rows)
    matched = ", ".join(
        f"{SURFACE_LABELS[surface]} matched {comparison.matched(surface)} / {total}" for surface in SURFACES
    )
    return f"Frontend: {matched} ({total} rows)"


def trees_line(comparison: FrontendComparison) -> str:
    """``Trees folded: tui abc (5), def (2); window abc (3)``: per surface, each tree and the table rows it covers.

    A surface with no result is omitted; ``none`` stands when no surface has one.
    """
    groups = []
    for surface in SURFACES:
        folded = comparison.trees_folded(surface)
        if folded:
            groups.append(f"{surface} " + ", ".join(f"{tree} ({count})" for tree, count in sorted(folded.items())))
    return "Trees folded: " + ("; ".join(groups) or "none")


__all__ = [
    "CELL_WORDS",
    "EXPORT_UNAVAILABLE",
    "EXPORT_WITHHELD_UNVERIFIED",
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
    "export_refusal_code",
    "extra_figures",
    "figure_causes",
    "frontend_line",
    "parity",
    "parse_result",
    "read_results",
    "row_cell",
    "trees_line",
]
