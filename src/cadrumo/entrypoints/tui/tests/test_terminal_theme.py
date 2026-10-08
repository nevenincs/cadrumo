"""The embedded surface leaves color resolution to the host terminal."""

from __future__ import annotations

import re
import sys
from io import StringIO

import pytest
from textual.widgets import Button, Input

from ..components.host import ScreenHostApp
from ..components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_TERMINAL, install_cadrumo_themes, toggle_appearance
from .terminal_theme_sample import ThemeSample, render_sample

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.asyncio]


async def test_embedded_widgets_emit_palette_colors_and_preserve_editing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Already drawn cells remain recolorable; no RGB styles pin them dark."""
    monkeypatch.setenv("TERM_PROGRAM", "cadrumo")
    monkeypatch.delenv("NO_COLOR", raising=False)
    output = await render_sample()
    assert "Existing content" in output
    assert "unsaved edit" in output
    assert not re.search(r"\x1b\[[\d;]*(?:38|48);[25];", output)
    app = ScreenHostApp(ThemeSample())
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        assert app.theme == CADRUMO_TERMINAL.name
        assert app.native_ansi_color
        assert app.screen.query_one(Button).styles.color.ansi == 0
        await pilot.press("end", "!")
        assert app.screen.query_one(Input).value == "unsaved edit!"
        # A headless host sends no terminal control and keeps the adaptive theme.
        assert toggle_appearance(app) == CADRUMO_TERMINAL.name
        assert app.screen.query_one(Input).value == "unsaved edit!"


async def test_standalone_tui_retains_its_own_theme_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary terminals are not bound to the desktop's private palette."""
    monkeypatch.setenv("TERM_PROGRAM", "WindowsTerminal")
    app = ScreenHostApp(ThemeSample())
    async with app.run_test():
        assert app.theme == CADRUMO_DARK_THEME_NAME
        assert toggle_appearance(app) == "cadrumo-light"
        assert not app.native_ansi_color


async def test_desktop_appearance_action_emits_only_the_bounded_presentation_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The action requests a frontend toggle without changing Textual's theme."""
    monkeypatch.setenv("TERM_PROGRAM", "cadrumo")
    output = StringIO()
    monkeypatch.setattr(sys, "__stdout__", output)
    app = ScreenHostApp(ThemeSample())
    install_cadrumo_themes(app)
    assert toggle_appearance(app) == CADRUMO_TERMINAL.name
    assert output.getvalue() == "\x1b]777;cadrumo;appearance;toggle\x1b\\"
