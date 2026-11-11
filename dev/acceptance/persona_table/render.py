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


def lane_counts(rows: Iterable[TableRow], lanes: Mapping[str, str]) -> dict[str, tuple[int, int]]:
    """Green and total rows per lane, the lane of a row being the one ``lanes`` maps its modelo to."""
    totals: dict[str, list[int]] = {}
    for row in rows:
        lane = lanes.get(row.modelo, "other")
        held = totals.setdefault(lane, [0, 0])
        held[1] += 1
        if row.verdict in GREEN:
            held[0] += 1
    return {lane: (green, total) for lane, (green, total) in sorted(totals.items())}


def summary_line(rows: list[TableRow]) -> str:
    """The summary sentence: green first, then every other verdict, then failing rows by stage."""
    counted = counts(rows)
    green = counted[Verdict.PASSED.value]
    parts = [f"green {green} / {len(rows)}"]
    parts += [f"{verdict.value} {counted[verdict.value]}" for verdict in Verdict if verdict is not Verdict.PASSED]
    parts += [f"red at {stage} {counted[f'fail:{stage}']}" for stage in ("calculate", "verify", "export")]
    return ", ".join(parts)


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_table(rows: Iterable[TableRow], *, head: str, lanes: Mapping[str, str] | None = None) -> str:
    """The full table for ``head`` as Markdown."""
    ordered = sorted(rows, key=lambda row: row.key)
    lines = [
        f"# Persona table at {head}",
        "",
        f"Summary: {summary_line(ordered)}.",
        "",
    ]
    if lanes is not None:
        lines += [
            "By lane (green/total, green = pass): "
            + ", ".join(f"{lane} {green}/{total}" for lane, (green, total) in lane_counts(ordered, lanes).items()),
            "",
        ]
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


__all__ = ["counts", "lane_counts", "red_stage", "render_table", "summary_line"]
