"""Compare two persona tables: rows that turned green, rows that regressed, and stage-level moves."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .rows import GREEN, Stage, TableRow

type RowKey = tuple[str, str, int, str]

_STAGE_GOOD = frozenset({Stage.PASSED, Stage.EXPECTED_REFUSAL})


def row_id(key: RowKey) -> str:
    """The row id ``persona|modelo|year|period``."""
    persona, modelo, year, period = key
    return f"{persona}|{modelo}|{year}|{period}"


@dataclass(frozen=True, slots=True)
class TableDiff:
    """The rows that moved between two tables."""

    turned_green: tuple[RowKey, ...]
    regressed: tuple[RowKey, ...]
    """Green before, not green now, or gone."""
    stage_regressed: tuple[tuple[RowKey, str], ...]
    """Not green either time, but a stage that passed before no longer does."""
    stage_improved: tuple[tuple[RowKey, str], ...]
    added: tuple[RowKey, ...]
    removed: tuple[RowKey, ...]


def _stages(row: TableRow) -> dict[str, bool]:
    return {name: getattr(row, name) in _STAGE_GOOD for name in ("calculate", "verify", "export")}


def diff_tables(before: Mapping[RowKey, TableRow], after: Mapping[RowKey, TableRow]) -> TableDiff:
    """What changed from ``before`` to ``after``, keyed by row."""
    turned_green: list[RowKey] = []
    regressed: list[RowKey] = []
    stage_regressed: list[tuple[RowKey, str]] = []
    stage_improved: list[tuple[RowKey, str]] = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        old_green = old is not None and old.verdict in GREEN
        new_green = new is not None and new.verdict in GREEN
        if old_green and not new_green:
            regressed.append(key)
        elif new_green and not old_green:
            turned_green.append(key)
        elif old is not None and new is not None and not old_green:
            was, now = _stages(old), _stages(new)
            for stage in was:
                if was[stage] and not now[stage]:
                    stage_regressed.append((key, stage))
                elif now[stage] and not was[stage]:
                    stage_improved.append((key, stage))
    return TableDiff(
        turned_green=tuple(turned_green),
        regressed=tuple(regressed),
        stage_regressed=tuple(stage_regressed),
        stage_improved=tuple(stage_improved),
        added=tuple(sorted(set(after) - set(before))),
        removed=tuple(sorted(set(before) - set(after))),
    )


def render_diff(diff: TableDiff, *, before: str, after: str) -> str:
    """The diff as Markdown."""
    lines = [f"# Persona table diff {before} -> {after}", ""]
    sections: tuple[tuple[str, list[str]], ...] = (
        ("Turned green", [row_id(key) for key in diff.turned_green]),
        ("Regressed (green before, not now)", [row_id(key) for key in diff.regressed]),
        ("Stage regressed (red both times)", [f"{row_id(key)} {stage}" for key, stage in diff.stage_regressed]),
        ("Stage improved (red both times)", [f"{row_id(key)} {stage}" for key, stage in diff.stage_improved]),
        ("Rows added", [row_id(key) for key in diff.added]),
        ("Rows removed", [row_id(key) for key in diff.removed]),
    )
    for title, items in sections:
        lines += [f"## {title} ({len(items)})", ""]
        lines += [f"- {item}" for item in items] or ["- none"]
        lines.append("")
    return "\n".join(lines)


__all__ = ["RowKey", "TableDiff", "diff_tables", "render_diff", "row_id"]
