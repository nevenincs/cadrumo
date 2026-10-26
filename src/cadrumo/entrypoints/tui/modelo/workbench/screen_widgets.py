"""Small reusable Textual widgets owned by the Modelo workbench."""

from __future__ import annotations

from typing import ClassVar, override

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.visual import VisualType
from textual.widgets import Static

from .keys import describe_bindings
from .screen_constants import (
    _SCROLL_LOCALE_KEY,
)


class NoticeLine(Static):
    """The workbench's notice line, which takes a line only while it says something."""

    @override
    def update(self, content: VisualType = "", *, layout: bool = True) -> None:
        """Say ``content``, showing the line only while there is something to say."""
        super().update(content, layout=layout)
        self.display = bool(str(content))


class SymbolsPanel(VerticalScroll):
    """The "Symbols and keys" panel, which scrolls with the arrow keys and says so in the footer."""

    BINDINGS: ClassVar = [Binding("up", "scroll_up", "", show=True, key_display="↑↓")]

    def describe_keys(self) -> None:
        """Name the scroll key in the language now on screen."""
        describe_bindings(self._bindings.key_to_bindings, {"up": _SCROLL_LOCALE_KEY})
