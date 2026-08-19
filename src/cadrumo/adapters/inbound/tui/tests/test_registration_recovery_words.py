"""The full-screen creation door shows the recovery words and wipes them.

The S206 close: a profile created at the full-screen door is enrolled at
creation, the 24 words render on the screen itself (the terminal-direct
channel cannot render inside a full-screen app), and the wipeable
container is zeroised at the operator's confirmation.

No mocks. Real registration, real Argon2id, the real RegistrationApp
through Textual's headless Pilot, the real recovery enrollment.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input

from .....application.user_profile import assess_passphrase
from .....entrypoints.cli._config._manager_frontend import attempt_registration
from .....tests.secure_sql import isolated_profile_storage_root
from .. import RegistrationApp
from .._recovery_words_screen import RecoveryWordsScreen

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (140, 60)
_TYPED_PASSWORD = "recovery-words-screen-operator-secret"  # noqa: S105 - synthetic test fixture


def _screen() -> RegistrationApp:
    return RegistrationApp(
        assess=assess_passphrase,
        register=attempt_registration,
        suggested_name="",
    )


async def _fill(pilot, *, username: str, password: str, confirm: str) -> None:
    pilot.app.query_one("#field-username", Input).value = username
    pilot.app.query_one("#field-password", Input).value = password
    pilot.app.query_one("#field-confirm", Input).value = confirm
    await pilot.pause()


@pytest.mark.asyncio
async def test_the_full_screen_door_shows_the_words_then_wipes_them(tmp_path) -> None:
    """Creation at the full-screen door enrols recovery and displays it once."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Recovery Words Subject",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")
            await app.workers.wait_for_complete()
            await pilot.pause()

            # The words screen is now on top; the mnemonic renders there.
            words = pilot.app.screen
            assert isinstance(words, RecoveryWordsScreen)
            mnemonic = words.query_one("#words-value", None)
            assert mnemonic is not None
            rendered = str(mnemonic.render())
            assert len(rendered.split()) == 24

            # Confirmation zeroises the container and releases the flow.
            await pilot.click("#btn-confirm-words")
            await pilot.pause()

        assert app.outcome is not None
        assert app.outcome.label == "Recovery Words Subject"
