"""A minimal application that carries one screen for a standalone run.

An area's entry surface is a screen so a root shell can navigate to it.
Some callers still open one surface as a whole process -- the development
harness, and the line-mode entry points that hand control to a single
full-screen task -- and this host is what those use. It holds no behaviour
of its own beyond mounting the screen and reporting its dismissal as the
process result, so a surface behaves identically whether it is navigated to
or opened alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App

from .theme import BASE_CSS, install_cadrumo_themes, tokenised

if TYPE_CHECKING:
    from textual.screen import Screen


class ScreenHostApp[ResultT](App[ResultT | None]):
    """Run exactly one screen as its own process."""

    CSS = tokenised(BASE_CSS)

    def __init__(self, screen: Screen[ResultT | None]) -> None:
        """Bind the one screen this host exists to run."""
        super().__init__()
        self._hosted_screen = screen

    @property
    def hosted_screen(self) -> Screen[ResultT | None]:
        """The screen under this host, for a caller that addresses it directly."""
        return self._hosted_screen

    async def on_mount(self) -> None:
        """Mount the screen and exit when it dismisses.

        Awaited rather than fired and forgotten: a caller that starts this
        host and immediately addresses a control would otherwise race the
        push and find only the host's own empty default screen.
        """
        install_cadrumo_themes(self)
        await self.push_screen(self._hosted_screen, self.exit)


__all__ = ["ScreenHostApp"]
