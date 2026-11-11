"""Render persona-table rows as Markdown, with a summary that counts each verdict apart."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping

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
    return "By lane (green/total, green = pass; unchecked rows in brackets): " + ", ".join(
        f"{lane} {green}/{total} (unchecked {unchecked})"
        for lane, (green, total, unchecked) in lane_counts(rows, lanes).items()
    )


def summary_line(rows: list[TableRow]) -> str:
    """The summary sentence: green first, then every other verdict, then failing rows by stage."""
    counted = counts(rows)
    green = counted[Verdict.PASSED.value]
    parts = [f"green {green} / {len(rows)}"]
    parts += [f"{verdict.value} {counted[verdict.value]}" for verdict in Verdict if verdict is not Verdict.PASSED]
    parts += [f"red at {stage} {counted[f'fail:{stage}']}" for stage in ("calculate", "verify", "export")]
    return ", ".join(parts)


def row_label(row: TableRow) -> str:
    """The row id ``persona|modelo|year|period``."""
    return f"{row.persona}|{row.modelo}|{row.year}|{row.period}"


def _unchecked_section(rows: Iterable[TableRow]) -> list[str]:
    """The rows whose stated values the table could not all compare, each with what it could not check."""
    held = [row for row in rows if row.verdict is Verdict.UNCHECKED]
    if not held:
        return []
    lines = [f"Unchecked ({len(held)}): stated values the table does not compare.", ""]
    lines += [f"- {row_label(row)}: {', '.join(row.unchecked)}" for row in held]
    return [*lines, ""]


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_table(
    rows: Iterable[TableRow],
    *,
    head: str,
    lanes: Mapping[str, str] | None = None,
    provenance: Mapping[str, str] | None = None,
) -> str:
    """The full table for ``head`` as Markdown, naming the run's tree and authority when ``provenance`` is given."""
    ordered = sorted(rows, key=lambda row: row.key)
    lines = [f"# Persona table at {head}", ""]
    if provenance:
        lines += [
            "Run provenance: " + ", ".join(f"{key} `{value}`" for key, value in sorted(provenance.items())) + ".",
            "",
        ]
    lines += [
        f"Summary: {summary_line(ordered)}.",
        "",
    ]
    if lanes is not None:
        lines += [lane_line(ordered, lanes), ""]
    lines += _unchecked_section(ordered)
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


__all__ = ["counts", "lane_counts", "lane_line", "red_stage", "render_table", "row_label", "summary_line"]
