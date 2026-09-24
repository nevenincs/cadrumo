"""Shared navigation step for screens that need an operator-selected filing year."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, override

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ....core.i18n.render import tr
from .app_access import TypedAppAccess


class FilingYearRouteScreen(TypedAppAccess, Screen[None]):
    """Open an injected screen for a visibly selected, validated year."""

    BINDINGS: ClassVar = [("escape", "app.pop_screen", "Back")]

    def __init__(self, *, screen_factory: Callable[[int], Screen[None]]) -> None:
        """Keep the destination factory isolated from the year input widget."""
        super().__init__(id="filing-year-route-screen")
        self._screen_factory = screen_factory

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.filing_year_route.prompt"))
        yield Input(placeholder="YYYY", id="filing-year-route-year", max_length=4)
        yield Button(tr("tui.filing_year_route.open"), id="filing-year-route-open")
        yield Static(id="filing-year-route-error", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open the selected year only after lexical validation."""
        if event.button.id != "filing-year-route-open":
            return
        value = self.query_one("#filing-year-route-year", Input).value.strip()
        if len(value) != 4 or not value.isascii() or not value.isdecimal() or int(value) < 1900:
            self.query_one("#filing-year-route-error", Static).update(tr("tui.filing_year_route.invalid"))
            return
        try:
            screen = self._screen_factory(int(value))
        except Exception:
            self.query_one("#filing-year-route-error", Static).update(tr("tui.filing_year_route.unavailable"))
            return
        self.app.push_screen(screen)
