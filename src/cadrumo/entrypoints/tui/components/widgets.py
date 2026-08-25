"""Reusable, state-free Textual widgets for Cadrumo surfaces."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, override

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.geometry import Size
from textual.widgets import DataTable, Static

from ....core.json_contract import Notice, NoticeSeverity, ResolvedNoticeAction


class ContentScroll(VerticalScroll, can_focus=False):
    """The scroll host every Cadrumo surface puts its content column in."""


class ContentDataTable[CellType](DataTable[CellType]):
    """A table that expands to its rows inside the shared scroll host."""

    def watch_virtual_size(self, size: Size) -> None:
        """Keep the layout box equal to the current rows and header."""
        self.styles.height = max(1, size.height)


_NOTICE_GLYPH: Final[dict[NoticeSeverity, str]] = {
    NoticeSeverity.INFO: "ⓘ",
    NoticeSeverity.WARNING: "⚠",
}


def _notice_action_target(notice: Notice) -> str | None:
    """Return the typed executable target supplied by a notice producer."""
    action = notice.action
    if not isinstance(action, ResolvedNoticeAction) or action.action.cli_path is None or action.argument_bindings:
        return None
    return "aeat " + " ".join(action.action.cli_path)


class NoticeBand(Vertical, can_focus=False):
    """Render already-resolved notices without adding interaction state."""

    def __init__(self, notices: Sequence[Notice], *, id: str | None = None) -> None:
        """Store the immutable notice projection for rendering."""
        super().__init__(id=id)
        self._notices = tuple(notices)

    @override
    def compose(self) -> ComposeResult:
        for index, notice in enumerate(self._notices):
            glyph = _NOTICE_GLYPH.get(notice.severity, "•")
            yield Static(
                f"{glyph} {notice.message}",
                classes=f"cadrumo-notice cadrumo-notice-{notice.severity.value}",
                id=f"notice-{index}",
                markup=False,
            )
            action_target = _notice_action_target(notice)
            if action_target is not None:
                yield Static(
                    action_target,
                    classes="cadrumo-notice-action",
                    id=f"notice-{index}-action",
                    markup=False,
                )


__all__ = ["ContentDataTable", "ContentScroll", "NoticeBand"]
