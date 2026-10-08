"""A passphrase screen keeps ownership of blocking rotation through unmount."""

from __future__ import annotations

import asyncio
from threading import Event
from uuid import uuid4

import pytest
from textual.widgets import Input

from .....application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from .....core.credentials import assess_profile_password
from ...components.host import ScreenHostApp
from ..passphrase import PassphraseChangeAttempt, PassphraseScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CURRENT = "synthetic-current-passphrase"
_NEW = "synthetic-replacement-passphrase"


@pytest.mark.asyncio
async def test_unmount_waits_for_one_blocking_attempt_without_publishing_late_success() -> None:
    started, release, finished = Event(), Event(), Event()
    calls: list[tuple[str, str, str]] = []
    profile_id = uuid4()

    def rotate(current: str, replacement: str, confirmation: str) -> PassphraseChangeAttempt:
        calls.append((current, replacement, confirmation))
        started.set()
        if not release.wait(5):
            raise TimeoutError("test rotation was not released")
        finished.set()
        return PassphraseChangeAttempt(
            outcome=ProfilePassphraseRotationOutcome(
                profile_id=str(profile_id),
                password_generation=2,
                dek_epoch_preserved=True,
                recovery_enrollment_retained=False,
            )
        )

    screen = PassphraseScreen(assess=assess_profile_password, rotate=rotate)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        screen.query_one("#field-current", Input).value = _CURRENT
        screen.query_one("#field-new", Input).value = _NEW
        screen.query_one("#field-confirm", Input).value = _NEW
        await pilot.click("#btn-change")
        assert all(field.value == "" for field in screen.query(Input))
        assert await asyncio.to_thread(started.wait, 5)

        screen.action_change()
        assert calls == [(_CURRENT, _NEW, _NEW)]
        unmounting = asyncio.ensure_future(app.pop_screen())
        try:
            await asyncio.sleep(0.05)
            assert not unmounting.done()
            assert not finished.is_set()
            assert screen.outcome is None
        finally:
            release.set()
        await asyncio.wait_for(unmounting, 5)
        await pilot.pause()
        assert finished.is_set()
        assert screen.outcome is None
        assert app.return_value is None


@pytest.mark.asyncio
async def test_completed_attempt_clears_masked_fields_and_returns_only_typed_outcome() -> None:
    profile_id = uuid4()
    outcome = ProfilePassphraseRotationOutcome(
        profile_id=str(profile_id),
        password_generation=2,
        dek_epoch_preserved=True,
        recovery_enrollment_retained=False,
    )
    screen = PassphraseScreen(
        assess=assess_profile_password,
        rotate=lambda _current, _replacement, _confirmation: PassphraseChangeAttempt(outcome=outcome),
    )
    app = ScreenHostApp(screen)
    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        screen.query_one("#field-current", Input).value = _CURRENT
        screen.query_one("#field-new", Input).value = _NEW
        screen.query_one("#field-confirm", Input).value = _NEW
        await pilot.click("#btn-change")
        assert all(field.value == "" for field in screen.query(Input))
        await asyncio.wait_for(screen.workers.wait_for_complete(), 5)
        assert screen.outcome == outcome
        assert app.return_value == outcome
