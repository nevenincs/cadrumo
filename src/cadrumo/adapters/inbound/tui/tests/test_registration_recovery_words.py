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
from textual.worker import WorkerCancelled

from .....application.user_profile import CommittedProfileRepository
from .....core import assess_profile_password
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
        assess=assess_profile_password,
        register=attempt_registration,
        suggested_name="",
    )


async def _fill(pilot, *, username: str, password: str, confirm: str) -> None:
    pilot.app.query_one("#field-username", Input).value = username
    pilot.app.query_one("#field-password", Input).value = password
    pilot.app.query_one("#field-confirm", Input).value = confirm
    await pilot.pause()


async def _wait_for_recovery_screen(pilot) -> RecoveryWordsScreen:
    for _ in range(100):
        if isinstance(pilot.app.screen, RecoveryWordsScreen):
            return pilot.app.screen
        await pilot.pause(0.1)
    raise AssertionError("recovery confirmation screen did not open")


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

            # The words screen is now on top; the mnemonic renders there.
            words = await _wait_for_recovery_screen(pilot)
            mnemonic = words.query_one("#words-value", None)
            assert mnemonic is not None
            rendered = str(mnemonic.render())
            assert len(rendered.split()) == 24
            assert not any(
                view.label == "Recovery Words Subject" for view in CommittedProfileRepository().list()
            )

            # Confirmation zeroises the container and releases the flow.
            words.query_one("#field-recovery-verification", Input).value = rendered
            await pilot.click("#btn-confirm-words")
            await app.workers.wait_for_complete()
            await pilot.pause()

        assert app.outcome is not None
        assert app.outcome.label == "Recovery Words Subject"


@pytest.mark.asyncio
async def test_cancelling_recovery_confirmation_publishes_no_capsule(tmp_path) -> None:
    """A displayed phrase is not enrollment until the operator confirms it."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Cancelled Recovery Subject",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")
            await _wait_for_recovery_screen(pilot)

            await pilot.click("#btn-cancel-words")
            await app.workers.wait_for_complete()
            await pilot.pause()

        assert app.outcome is None
        assert not any(
            view.label == "Cancelled Recovery Subject" for view in CommittedProfileRepository().list()
        )


@pytest.mark.asyncio
async def test_wrong_recovery_reentry_publishes_no_capsule(tmp_path) -> None:
    """The masked control proves the exact ordered phrase, not button intent."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Wrong Recovery Reentry",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")
            words = await _wait_for_recovery_screen(pilot)
            words.query_one("#field-recovery-verification", Input).value = "not the displayed phrase"
            await pilot.click("#btn-confirm-words")
            await app.workers.wait_for_complete()
            await pilot.pause()

        assert app.outcome is None
        assert not any(view.label == "Wrong Recovery Reentry" for view in CommittedProfileRepository().list())


@pytest.mark.asyncio
async def test_app_shutdown_releases_pending_handoff_without_publication(tmp_path) -> None:
    """Stopping the message loop cannot strand the registration worker."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Shutdown Recovery Subject",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")
            await _wait_for_recovery_screen(pilot)
            app.exit(None)
            with pytest.raises(WorkerCancelled):
                await app.workers.wait_for_complete()
        assert not any(
            view.label == "Shutdown Recovery Subject" for view in CommittedProfileRepository().list()
        )
