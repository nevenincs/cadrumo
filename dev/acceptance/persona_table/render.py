"""Render persona-table rows as Markdown, with a summary that counts each verdict apart."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

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


def load_coverage_gaps(path: Path) -> tuple[CoverageGap, ...]:
    """The gaps of a coverage JSON (a ``gaps`` list of persona, modelo, year, period), refusing a malformed file."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"coverage file {path} is unreadable: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("gaps"), list):
        raise ValueError(f"coverage file {path} must be an object with a 'gaps' list")
    gaps: list[CoverageGap] = []
    for index, item in enumerate(document["gaps"]):
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
            raise ValueError(
                f"coverage file {path}: gap {index} needs text persona, modelo and period and an integer year"
            )
        gaps.append(CoverageGap(item["persona"], item["modelo"], year, item["period"]))
    return tuple(gaps)


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


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_table(
    rows: Iterable[TableRow],
    *,
    head: str,
    lanes: Mapping[str, str] | None = None,
    provenance: Mapping[str, str] | None = None,
    coverage_gaps: Sequence[CoverageGap] | None = None,
) -> str:
    """The full table for ``head`` as Markdown, naming the run's tree and authority when ``provenance`` is given.

    ``coverage_gaps`` is ``None`` when no coverage audit was supplied, which the rows line says.
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
        "",
    ]
    if lanes is not None:
        lines += [lane_line(ordered, lanes), ""]
    lines += _unchecked_section(ordered)
    lines += _gap_section(coverage_gaps)
    lines += ["Verdicts:", ""]
    lines += [f"- `{verdict.value}`: {meaning}." for verdict, meaning in VERDICT_MEANING.items()]
    lines += [
        "",
        "Each year is replayed with the registry horizon moved to it (column `run`); the real horizon wins a tie.",
        "",
        "| persona | modelo | year | period | verdict | calculate | verify | export | grounding | run | reason |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
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
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "CoverageGap",
    "counts",
    "lane_counts",
    "lane_line",
    "load_coverage_gaps",
    "red_stage",
    "render_table",
    "row_label",
    "rows_line",
    "summary_line",
    "unchecked_causes",
]
