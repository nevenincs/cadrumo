"""What every symbol on the workbench means, one key away and built from the marks the screen draws.

The filer never has to remember a glyph. Pressing ``?`` once opens the help
band, whose first line names only the symbols now on screen, each with how
often it appears; pressing it again opens "Symbols and keys" under the header:
the symbols on screen first, then every symbol the workbench can draw,
grouped, each with its name, a one-line meaning and the key that acts on it.

The legend is built from :mod:`.vocabulary`'s marks, so it cannot drift from
the screen, and the module refuses at import a mark the legend does not
explain, or an explanation of a mark nobody draws.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from rich.text import Text

from .....application.modelo.work_form_models import ModeloFormOrigin
from .....core.i18n.render import tr
from .vocabulary import (
    ATTENTION_MARKS,
    BLOCKS_MARK,
    CHECK_MARK,
    COLLAPSED_MARK,
    DONE_MARK,
    EARLIER_FILING_MARK,
    EXPANDED_MARK,
    HERE_MARK,
    INFO_MARK,
    ORIGIN_MARKS,
    STALE_MARK,
    WORKBENCH_MARKS,
    Attention,
    WorkbenchMark,
)

_ENTRY_SEPARATOR: Final[str] = " · "
_RULE: Final[str] = "──"


@dataclass(frozen=True, slots=True)
class LegendEntry:
    """One symbol in the legend: its mark, what it means and the key that acts on it, if any."""

    mark: WorkbenchMark
    meaning_key: str
    key: str | None = None


@dataclass(frozen=True, slots=True)
class LegendGroup:
    """Symbols that answer one question, under a heading."""

    heading_key: str
    entries: tuple[LegendEntry, ...]


def _origin(origin: ModeloFormOrigin, meaning_key: str, key: str | None = None) -> LegendEntry:
    return LegendEntry(ORIGIN_MARKS[origin], meaning_key, key)


LEGEND_LOCALE_KEYS: Final[tuple[LegendGroup, ...]] = (
    LegendGroup(
        "tui.modelo.workbench.legend.group.needs_you",
        (
            LegendEntry(BLOCKS_MARK, "tui.modelo.workbench.legend.meaning.level.blocks", "i"),
            _origin(ModeloFormOrigin.NEEDS_INPUT, "tui.modelo.workbench.legend.meaning.origin.needs_input", "n"),
            _origin(
                ModeloFormOrigin.DEFAULT_TO_CONFIRM,
                "tui.modelo.workbench.legend.meaning.origin.default_to_confirm",
                "b",
            ),
            _origin(
                ModeloFormOrigin.CALCULATION_FAILED,
                "tui.modelo.workbench.legend.meaning.origin.calculation_failed",
                "i",
            ),
            LegendEntry(CHECK_MARK, "tui.modelo.workbench.legend.meaning.level.check"),
            LegendEntry(INFO_MARK, "tui.modelo.workbench.legend.meaning.level.info"),
        ),
    ),
    LegendGroup(
        "tui.modelo.workbench.legend.group.origin",
        (
            _origin(ModeloFormOrigin.ENTERED, "tui.modelo.workbench.legend.meaning.origin.entered"),
            _origin(ModeloFormOrigin.OVERRIDES_SOURCE, "tui.modelo.workbench.legend.meaning.origin.overrides_source"),
            _origin(ModeloFormOrigin.CALCULATED, "tui.modelo.workbench.legend.meaning.origin.calculated"),
            _origin(ModeloFormOrigin.IMPORTED, "tui.modelo.workbench.legend.meaning.origin.imported"),
            LegendEntry(EARLIER_FILING_MARK, "tui.modelo.workbench.legend.meaning.mark.earlier"),
            _origin(ModeloFormOrigin.INFORMATIONAL, "tui.modelo.workbench.legend.meaning.origin.informational"),
        ),
    ),
    LegendGroup(
        "tui.modelo.workbench.legend.group.empty",
        (
            _origin(ModeloFormOrigin.OPTIONAL_EMPTY, "tui.modelo.workbench.legend.meaning.origin.optional_empty"),
            _origin(ModeloFormOrigin.CLEARED, "tui.modelo.workbench.legend.meaning.origin.cleared"),
            _origin(ModeloFormOrigin.NOT_APPLICABLE, "tui.modelo.workbench.legend.meaning.origin.not_applicable"),
            _origin(
                ModeloFormOrigin.NOT_CALCULATED_YET, "tui.modelo.workbench.legend.meaning.origin.not_calculated_yet"
            ),
            _origin(ModeloFormOrigin.NOT_IMPORTED_YET, "tui.modelo.workbench.legend.meaning.origin.not_imported_yet"),
        ),
    ),
    LegendGroup(
        "tui.modelo.workbench.legend.group.progress",
        (
            LegendEntry(ATTENTION_MARKS[Attention.STAGED], "tui.modelo.workbench.legend.meaning.mark.staged", "R"),
            LegendEntry(STALE_MARK, "tui.modelo.workbench.legend.meaning.mark.stale", "R"),
            LegendEntry(DONE_MARK, "tui.modelo.workbench.legend.meaning.mark.done"),
            LegendEntry(HERE_MARK, "tui.modelo.workbench.legend.meaning.mark.here"),
            LegendEntry(COLLAPSED_MARK, "tui.modelo.workbench.legend.meaning.mark.collapsed"),
            LegendEntry(EXPANDED_MARK, "tui.modelo.workbench.legend.meaning.mark.expanded"),
        ),
    ),
)
"""Every symbol the workbench draws, grouped by the question it answers, in the order the panel lists them."""

_MARKS_BY_GLYPH: Final[dict[str, WorkbenchMark]] = {mark.glyph: mark for mark in WORKBENCH_MARKS}
_ORDER: Final[dict[str, int]] = {
    entry.mark.glyph: position
    for position, entry in enumerate(entry for group in LEGEND_LOCALE_KEYS for entry in group.entries)
}


def mark_for_glyph(glyph: str) -> WorkbenchMark:
    """The mark a drawn glyph stands for; every glyph the workbench draws has exactly one."""
    return _MARKS_BY_GLYPH[glyph]


def legend_glyphs() -> frozenset[str]:
    """Every glyph the legend explains."""
    return frozenset(_ORDER)


def on_screen(marks: Iterable[WorkbenchMark]) -> tuple[tuple[WorkbenchMark, int], ...]:
    """The marks drawn now, each once with how often it is drawn, in the legend's order."""
    counted = Counter(marks)
    return tuple(sorted(counted.items(), key=lambda pair: _ORDER[pair[0].glyph]))


def on_screen_text(marks: Iterable[WorkbenchMark]) -> str:
    """The help band's first line: the symbols on screen with their names and counts."""
    entries = _ENTRY_SEPARATOR.join(
        f"{mark.glyph} {tr(mark.translation_key)} {count}" for mark, count in on_screen(marks)
    )
    return f"{tr('tui.modelo.workbench.legend.on_screen')}: {entries}"


def more_text() -> str:
    """The line that says the next ``?`` opens every symbol and key."""
    return tr("tui.modelo.workbench.legend.more")


def first_open_text() -> str:
    """The notice a filer sees the first time the workbench opens in a session."""
    return tr("tui.modelo.workbench.legend.first_open")


def _heading(text: str) -> Text:
    return Text(f"{_RULE} {text} {_RULE}", style="bold")


def legend_panel(marks: Iterable[WorkbenchMark], *, keys: str, close: str) -> Text:
    """The full "Symbols and keys" reference: what is on screen, then every symbol, then the keys."""
    panel = Text()
    panel.append(f"{tr('tui.modelo.workbench.legend.title')}   {close}\n", style="bold")
    panel.append(f"{tr('tui.modelo.workbench.legend.intro')}\n")
    shown = on_screen(marks)
    if shown:
        panel.append_text(_heading(tr("tui.modelo.workbench.legend.on_screen")))
        panel.append("\n")
        panel.append(
            _ENTRY_SEPARATOR.join(f"{mark.glyph} {tr(mark.translation_key)} {count}" for mark, count in shown) + "\n"
        )
    for group in LEGEND_LOCALE_KEYS:
        panel.append_text(_heading(tr(group.heading_key)))
        panel.append("\n")
        for entry in group.entries:
            key = f"  [{entry.key}]" if entry.key else ""
            panel.append(f" {entry.mark.glyph} {tr(entry.mark.translation_key)}: {tr(entry.meaning_key)}{key}\n")
    panel.append_text(_heading(tr("tui.modelo.workbench.legend.group.keys")))
    panel.append(f"\n{keys}")
    return panel


def _require_every_mark_explained() -> None:
    """Refuse a legend that leaves a drawn mark unexplained, or explains a mark nobody draws."""
    explained = [entry.mark for group in LEGEND_LOCALE_KEYS for entry in group.entries]
    if len(explained) != len(set(explained)):
        raise ValueError("the legend explains a mark twice")
    if set(explained) != set(WORKBENCH_MARKS):
        missing = sorted(mark.glyph for mark in set(WORKBENCH_MARKS) - set(explained))
        extra = sorted(mark.glyph for mark in set(explained) - set(WORKBENCH_MARKS))
        raise ValueError(f"the legend and the workbench's marks disagree: missing {missing}, extra {extra}")


_require_every_mark_explained()


__all__ = [
    "LEGEND_LOCALE_KEYS",
    "LegendEntry",
    "LegendGroup",
    "first_open_text",
    "legend_glyphs",
    "legend_panel",
    "mark_for_glyph",
    "more_text",
    "on_screen",
    "on_screen_text",
]
