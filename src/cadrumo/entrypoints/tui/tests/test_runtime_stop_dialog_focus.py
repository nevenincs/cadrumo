"""The destructive runtime-stop dialog opens on its safe declining action."""

import pytest
from textual.app import App
from textual.widgets import Button

from ..runtime_management import RuntimeStopConfirmationScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_runtime_stop_dialog_focuses_decline_and_enter_does_not_confirm() -> None:
    app = App[None]()
    dismissed: list[bool | None] = []

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.push_screen(RuntimeStopConfirmationScreen(), dismissed.append)
        await pilot.pause()

        assert app.focused is app.screen.query_one("#runtime-stop-cancel", Button)
        await pilot.press("enter")
        await pilot.pause()
        assert dismissed == [False]
        app.exit(None)
