"""Press a capture host's button once the previous step has made it pressable."""

from __future__ import annotations

from textual.app import App
from textual.dom import DOMNode
from textual.widgets import Button

from cadrumo.entrypoints.tui.tests.settling import settle_host, settle_host_until


async def press_when_enabled[ResultT](app: App[ResultT], button_id: str, *, within: DOMNode | None = None) -> None:
    """Press ``#button_id`` once it is shown and enabled, then settle what the press started.

    ``Button.press`` silently ignores a disabled or hidden button, so pressing
    before the previous step enabled it would capture the wrong state rather
    than fail. ``within`` defaults to the active screen at each check, which
    is where a dialog pushed by the previous step lives.
    """
    selector = f"#{button_id}"

    def pressable() -> bool:
        scope = app.screen if within is None else within
        return any(not button.disabled and button.display for button in scope.query(selector).results(Button))

    await settle_host_until(app, pressable, f"{selector} to be shown and enabled")
    (app.screen if within is None else within).query_one(selector, Button).press()
    await settle_host(app)


__all__ = ["press_when_enabled"]
