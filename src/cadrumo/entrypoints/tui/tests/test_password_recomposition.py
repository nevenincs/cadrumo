"""An expired old lease cannot erase a password change still settling."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Never
from uuid import uuid4

import pytest
from textual.widgets import Input

from ....application.overview.home import HomeAccountSession, HomeSessionPosture
from ....application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from ....core.credentials import assess_profile_password
from ..account import (
    AccountDirectSessionActionV1,
    AccountFactoriesV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
)
from ..app import CadrumoTuiApp
from ..components.account_chrome import AccountActionV1
from ..secret.passphrase import PassphraseChangeAttempt, PassphraseChangeRefusal, PassphraseScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CURRENT = "synthetic-current-passphrase"
_NEW = "synthetic-replacement-passphrase"


def _unavailable(*_args: object, **_kwargs: object) -> Never:
    raise AssertionError("an unrelated account door was opened")


@pytest.mark.asyncio
@pytest.mark.parametrize("completion", ["success", "refusal", "error"])
async def test_expiry_hides_private_screen_but_waits_for_rotation_result(completion: str) -> None:
    started, release, finished = Event(), Event(), Event()
    reads = 0
    outcome = ProfilePassphraseRotationOutcome(
        profile_id=str(uuid4()),
        password_generation=2,
        dek_epoch_preserved=True,
        recovery_enrollment_retained=False,
    )

    def rotate(_current: str, _replacement: str, _confirmation: str) -> PassphraseChangeAttempt:
        started.set()
        if not release.wait(5):
            raise TimeoutError("test rotation was not released")
        finished.set()
        if completion == "success":
            return PassphraseChangeAttempt(outcome=outcome)
        if completion == "refusal":
            return PassphraseChangeAttempt(
                expected_refusal=PassphraseChangeRefusal(message_key="flows.passphrase.refusal.change_failed")
            )
        raise RuntimeError("synthetic rotation refusal")

    async def read_session() -> HomeAccountSession:
        nonlocal reads
        reads += 1
        raise AccountSessionExpiredError("old session retired")

    screen = PassphraseScreen(assess=assess_profile_password, rotate=rotate)

    async def unrelated_session_completion() -> AccountRecomposeRequiredV1:
        raise AssertionError("an unrelated account door was opened")

    unrelated_action = AccountDirectSessionActionV1(complete=unrelated_session_completion)
    factories = AccountFactoriesV1(
        profile=_unavailable,
        change_user=lambda: unrelated_action,
        password=lambda: screen,
        appearance=_unavailable,
        language=_unavailable,
        sign_out=lambda: unrelated_action,
    )
    app = CadrumoTuiApp(account_factories=factories, read_account_session=read_session)
    initial = HomeAccountSession(
        posture=HomeSessionPosture.ACTIVE,
        profile_label="Current profile",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    async with app.run_test(size=(100, 36)) as pilot:
        app._account_session = initial
        app.run_account_action(AccountActionV1.PASSWORD)
        await pilot.pause()
        assert app.screen is screen
        screen.query_one("#field-current", Input).value = _CURRENT
        screen.query_one("#field-new", Input).value = _NEW
        screen.query_one("#field-confirm", Input).value = _NEW
        await pilot.click("#btn-change")
        assert await asyncio.to_thread(started.wait, 5)
        assert all(field.value == "" for field in screen.query(Input))

        app._watch_account_session()
        async with asyncio.timeout(5):
            while app._account_factories is not None:
                await pilot.pause(0.02)
        assert reads == 1
        assert app.account_session is None
        assert app._read_account_session is None
        assert app._account_factories is None
        assert not screen.display
        assert app.return_value is None
        app._watch_account_session()
        await pilot.pause()
        assert reads == 1
        assert not finished.is_set()

        release.set()
        async with asyncio.timeout(5):
            while app.return_value is None:
                await pilot.pause(0.02)
        assert finished.is_set()
        assert app.return_value == AccountRecomposeRequiredV1(
            reason=(
                AccountRecomposeReasonV1.PASSWORD_CHANGED
                if completion == "success"
                else AccountRecomposeReasonV1.EXPIRED
            )
        )
