"""Pilot-driven proof for the reusable confirmation dialog."""

import pytest
from textual.app import App

from ...tests.settling import settle
from ..dialogs import ConfirmScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_confirmation_dialog_defaults_to_decline_and_requires_explicit_acceptance() -> None:
    app = App[None]()
    dismissed: list[bool | None] = []

    async with app.run_test(size=(140, 60)) as pilot:
        await settle(pilot)
        app.push_screen(
            ConfirmScreen(
                title="Restart?", message="Answers will be cleared.", confirm_label="Restart", cancel_label="Keep"
            ),
            dismissed.append,
        )
        await settle(pilot)

        assert app.focused is app.screen.query_one("#btn-confirm-cancel")
        await pilot.press("y")
        await settle(pilot)
        assert dismissed == [True]
        app.exit(None)
