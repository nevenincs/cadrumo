"""The header's result line at the top of a dialog that covers the header.

It takes one line at any width and draws each chip in its level's colour, as
the header does, so the result and what is left to do stay in view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual import events
from textual.widgets import Static

from ...components.theme import tokenised

if TYPE_CHECKING:
    from .header import StatusLine


class StatusBar(Static):
    """One line repeating the header's result and chips, fitted again whenever its width changes."""

    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        StatusBar {
            height: $cadrumo-band-height;
        }
        """
    )

    def __init__(self, status: StatusLine, *, id: str | None = None) -> None:
        """Hold the line to repeat, first fitted to the whole terminal."""
        super().__init__(id=id)
        self._status = status

    def on_mount(self) -> None:
        """Fit the line to the width the dialog gives it."""
        self.update(self._status.content(self.content_size.width or self.app.size.width))

    def on_resize(self, event: events.Resize) -> None:
        """Fit the line again to the new width."""
        self.update(self._status.content(event.size.width))


__all__ = ["StatusBar"]
