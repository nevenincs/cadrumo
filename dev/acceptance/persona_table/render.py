"""Render persona-table rows as Markdown, with a summary that counts each verdict apart."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .diff import row_id
from .frontend import (
    DIFFERS,
    EXTRA,
    NOT_COMPARABLE,
    SURFACE_LABELS,
    SURFACES,
    FrontendComparison,
    cell_text,
    frontend_line,
    row_cell,
)
from .rows import GREEN, VERDICT_MEANING, Stage, TableRow, Verdict

_RED_CALCULATE = frozenset({Stage.MISMATCH, Stage.REFUSED, Stage.REFUSAL_NOT_RAISED})


def red_stage(row: TableRow) -> str | None:
    """The first stage a failing row is red at."""
    if row.verdict is not Verdict.FAIL:
        return None
    if row.calculate in _RED_CALCULATE:
        return "calculate"
    if row.verify is not Stage.PASSED:
        return "verify"
    return "export"


def counts(rows: Iterable[TableRow]) -> Counter[str]:
    """Rows per verdict, and failing rows per first red stage under ``fail:<stage>``."""
    counted: Counter[str] = Counter()
    for row in rows:
        counted[row.verdict.value] += 1
        stage = red_stage(row)
        if stage is not None:
            counted[f"fail:{stage}"] += 1
    return counted


def lane_counts(rows: Iterable[TableRow], lanes: Mapping[str, str]) -> dict[str, tuple[int, int, int]]:
    """Green, total and unchecked rows per lane, the lane of a row being the one ``lanes`` maps its modelo to."""
    totals: dict[str, list[int]] = {}
    for row in rows:
        held = totals.setdefault(lanes.get(row.modelo, "other"), [0, 0, 0])
        held[0] += row.verdict in GREEN
        held[1] += 1
        held[2] += row.verdict is Verdict.UNCHECKED
    return {lane: (green, total, unchecked) for lane, (green, total, unchecked) in sorted(totals.items())}


def lane_line(rows: Iterable[TableRow], lanes: Mapping[str, str]) -> str:
    """The per-lane sentence: each lane's green and total rows, and its rows held back as unchecked."""
    return "By lane (green/total, green = pass or not-owed; unchecked rows in brackets): " + ", ".join(
        f"{lane} {green}/{total} (unchecked {unchecked})"
        for lane, (green, total, unchecked) in lane_counts(rows, lanes).items()
    )


def summary_line(rows: list[TableRow]) -> str:
    """The summary sentence: green (each ``GREEN`` verdict) first, then every other verdict, then red rows by stage."""
    counted = counts(rows)
    green = sum(counted[verdict.value] for verdict in GREEN)
    parts = [f"green {green} / {len(rows)}"]
    parts += [f"{verdict.value} {counted[verdict.value]}" for verdict in Verdict if verdict is not Verdict.PASSED]
    parts += [f"red at {stage} {counted[f'fail:{stage}']}" for stage in ("calculate", "verify", "export")]
    return ", ".join(parts)


def row_label(row: TableRow) -> str:
    """The row id ``persona|modelo|year|period``."""
    return f"{row.persona}|{row.modelo}|{row.year}|{row.period}"


def unchecked_causes(rows: Iterable[TableRow]) -> dict[str, int]:
    """Unchecked rows per cause, the cause being an item's kind (``not-sourced``, ``concept``, ``role``, ...).

    A row holding items of several kinds counts under each, so the counts may sum above the unchecked rows.
    """
    counted = Counter(
        cause
        for row in rows
        if row.verdict is Verdict.UNCHECKED
        for cause in {item.split(":", 1)[0] for item in row.unchecked}
    )
    return dict(sorted(counted.items()))


def _unchecked_section(rows: Iterable[TableRow]) -> list[str]:
    """The rows whose stated values the table could not all compare, each with what it could not check."""
    held = [row for row in rows if row.verdict is Verdict.UNCHECKED]
    if not held:
        return []
    causes = ", ".join(f"{cause} {count}" for cause, count in unchecked_causes(held).items())
    lines = [
        f"Unchecked ({len(held)}): stated values the table does not compare.",
        "",
        f"Unchecked rows by cause (a row with several causes counts under each): {causes}.",
        "",
    ]
    lines += [f"- {row_label(row)}: {', '.join(row.unchecked)}" for row in held]
    return [*lines, ""]


@dataclass(frozen=True)
class CoverageGap:
    """A return the application's own calendar marks applicable that the table does not run."""

    persona: str
    modelo: str
    year: int
    period: str

    @property
    def label(self) -> str:
        """The gap id ``persona|modelo|year|period``, spelled as a row id."""
        return f"{self.persona}|{self.modelo}|{self.year}|{self.period}"


@dataclass(frozen=True)
class UndecidedObligation:
    """A return the application's calendar can neither mark owed nor not owed, with the calendar's reason."""

    obligation: CoverageGap
    reason: str
    in_table: bool


def _coverage_list(path: Path, key: str) -> list[object]:
    """One list of a coverage JSON, refusing an unreadable file or one whose ``key`` is not a list."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"coverage file {path} is unreadable: {error}") from error
    items: object = document.get(key) if isinstance(document, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"coverage file {path} must be an object with a '{key}' list")
    return cast("list[object]", items)


def load_coverage_gaps(path: Path) -> tuple[CoverageGap, ...]:
    """The gaps of a coverage JSON (a ``gaps`` list of persona, modelo, year, period), refusing a malformed file."""
    return tuple(_coverage_gap(path, index, item) for index, item in enumerate(_coverage_list(path, "gaps")))


def load_coverage_undecided(path: Path) -> tuple[UndecidedObligation, ...]:
    """The undecided obligations of a coverage JSON, each with the calendar's reason and whether the table runs it."""
    return tuple(_undecided(path, index, item) for index, item in enumerate(_coverage_list(path, "undecided")))


def _undecided(path: Path, index: int, item: object) -> UndecidedObligation:
    """One undecided obligation, refusing an item without a text reason and a boolean ``in_table``."""
    obligation = _coverage_gap(path, index, item)
    fields = cast("dict[str, object]", item)
    reason, in_table = fields.get("reason"), fields.get("in_table")
    if not isinstance(reason, str) or not isinstance(in_table, bool):
        raise ValueError(f"coverage file {path}: undecided {index} needs a text reason and a boolean in_table")
    return UndecidedObligation(obligation, reason, in_table)


def _coverage_gap(path: Path, index: int, item: object) -> CoverageGap:
    """One gap of a coverage file, refusing an item that is not an object of text keys and an integer year."""
    if not isinstance(item, dict):
        raise ValueError(f"coverage file {path}: gap {index} must be an object")
    missing = [key for key in ("persona", "modelo", "year", "period") if key not in item]
    if missing:
        raise ValueError(f"coverage file {path}: gap {index} lacks {', '.join(missing)}")
    year = item["year"]
    if (
        not isinstance(year, int)
        or isinstance(year, bool)
        or not all(isinstance(item[key], str) for key in ("persona", "modelo", "period"))
    ):
        raise ValueError(f"coverage file {path}: gap {index} needs text persona, modelo and period and an integer year")
    return CoverageGap(item["persona"], item["modelo"], year, item["period"])


def rows_line(rows: Sequence[TableRow], coverage_gaps: Sequence[CoverageGap] | None) -> str:
    """The ``rows expected / rows run`` sentence; expected adds the coverage gaps to the table's planned rows."""
    run = sum(row.verdict is not Verdict.NOT_RUN for row in rows)
    if coverage_gaps is None:
        return f"Rows: expected {len(rows)} (table plan only; no coverage audit) / run {run}"
    return f"Rows: expected {len(rows) + len(coverage_gaps)} / run {run}"


def _gap_section(coverage_gaps: Sequence[CoverageGap] | None) -> list[str]:
    if coverage_gaps is None or len(coverage_gaps) == 0:
        return []
    lines = [f"## Coverage gaps ({len(coverage_gaps)})", ""]
    lines += [f"- {label}" for label in sorted(gap.label for gap in coverage_gaps)]
    return [*lines, ""]


def _undecided_section(undecided: Sequence[UndecidedObligation] | None) -> list[str]:
    if undecided is None or len(undecided) == 0:
        return []
    lines = [
        f"## Undecided obligations ({len(undecided)})",
        "",
        "The calendar can neither mark these returns owed nor not owed; they count in no expected figure.",
        "",
    ]
    for item in sorted(undecided, key=lambda entry: entry.obligation.label):
        where = "run in the table" if item.in_table else "not run"
        lines.append(f"- {item.obligation.label}: {item.reason} ({where})")
    return [*lines, ""]


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_table(
    rows: Iterable[TableRow],
    *,
    head: str,
    lanes: Mapping[str, str] | None = None,
    provenance: Mapping[str, str] | None = None,
    coverage_gaps: Sequence[CoverageGap] | None = None,
    undecided: Sequence[UndecidedObligation] | None = None,
    frontend: FrontendComparison | None = None,
) -> str:
    """The full table for ``head`` as Markdown, naming the run's tree and authority when ``provenance`` is given.

    ``coverage_gaps`` is ``None`` when no coverage audit was supplied, which the rows line says; ``undecided`` lists the
    returns that audit could not decide. ``frontend`` adds a column per surface, a summary line and the frontend matrix.
    """
    ordered = sorted(rows, key=lambda row: row.key)
    lines = [f"# Persona table at {head}", ""]
    if provenance is not None and provenance:
        lines += [
            "Run provenance: " + ", ".join(f"{key} `{value}`" for key, value in sorted(provenance.items())) + ".",
            "",
        ]
    lines += [
        f"Summary: {summary_line(ordered)}.",
        rows_line(ordered, coverage_gaps),
    ]
    if frontend is not None:
        lines.append(frontend_line(frontend))
    lines.append("")
    if lanes is not None:
        lines += [lane_line(ordered, lanes), ""]
    lines += _unchecked_section(ordered)
    lines += _gap_section(coverage_gaps)
    lines += _undecided_section(undecided)
    lines += ["Verdicts:", ""]
    lines += [f"- `{verdict.value}`: {meaning}." for verdict, meaning in VERDICT_MEANING.items()]
    lines += [
        "",
        "Each year is replayed with the registry horizon moved to it (column `run`); the real horizon wins a tie.",
        "",
        "| persona | modelo | year | period | verdict | calculate | verify | export | grounding | run | reason |"
        + ("".join(f" {surface} |" for surface in SURFACES) if frontend is not None else ""),
        "|---|---|---|---|---|---|---|---|---|---|---|" + ("---|" * len(SURFACES) if frontend is not None else ""),
    ]
    cells = _frontend_cells(frontend, head)
    for row in ordered:
        export = row.export.value + (f" ({row.export_detail})" if row.export_detail else "")
        lines.append(
            "| "
            + " | ".join(
                _cell(item)
                for item in (
                    row.persona,
                    row.modelo,
                    row.year,
                    row.period,
                    row.verdict.value,
                    row.calculate.value,
                    row.verify.value,
                    export,
                    row.grounding,
                    row.horizon,
                    row.reason,
                    *cells.get(row.key, ()),
                )
            )
            + " |"
        )
    if frontend is not None:
        lines += _frontend_section(frontend)
    return "\n".join(lines) + "\n"


def _frontend_cells(frontend: FrontendComparison | None, head: str) -> dict[tuple[str, str, int, str], list[str]]:
    """Each table row's cell per surface, in ``SURFACES`` order."""
    cells: dict[tuple[str, str, int, str], list[str]] = {}
    if frontend is None:
        return cells
    for surface in SURFACES:
        for item in frontend.parities[surface]:
            cells.setdefault(item.key, []).append(row_cell(item, head))
    return cells


def _frontend_section(frontend: FrontendComparison) -> list[str]:
    """The matrix of each persona on each surface, then the rows that did not match with their causes."""
    lines = [
        "",
        "## Frontend matrix",
        "",
        "| persona | " + " | ".join(SURFACE_LABELS[surface] for surface in SURFACES) + " |",
        "|---|" + "---|" * len(SURFACES),
    ]
    for persona in frontend.personas():
        cells = [persona, *(cell_text(frontend.cells[persona, surface]) for surface in SURFACES)]
        lines.append("| " + " | ".join(_cell(item) for item in cells) + " |")
    lines += ["", "### Rows differing", ""]
    causes: dict[tuple[str, str, int, str], list[str]] = {}
    for surface in SURFACES:
        for item in (*frontend.parities[surface], *frontend.extras[surface]):
            if item.outcome in (DIFFERS, NOT_COMPARABLE, EXTRA):
                causes.setdefault(item.key, []).append(f"{surface} {item.outcome}: {'; '.join(item.causes)}")
    lines += [f"- {row_id(key)}: {' / '.join(found)}" for key, found in sorted(causes.items())] or ["- none"]
    return lines


__all__ = [
    "CoverageGap",
    "UndecidedObligation",
    "counts",
    "lane_counts",
    "lane_line",
    "load_coverage_gaps",
    "load_coverage_undecided",
    "red_stage",
    "render_table",
    "row_label",
    "rows_line",
    "summary_line",
    "unchecked_causes",
]
