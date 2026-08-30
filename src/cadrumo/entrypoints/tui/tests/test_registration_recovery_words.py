"""The full-screen creation door shows the recovery words and wipes them.

The security boundary: a profile created at the full-screen door is enrolled at
creation, the 24 words render on the screen itself (the terminal-direct
channel cannot render inside a full-screen app), and the wipeable
container is zeroised at the operator's confirmation.

No mocks. Real registration, real Argon2id, the real RegistrationScreen
through Textual's headless Pilot, the real recovery enrollment.
"""

from __future__ import annotations

from time import monotonic

import pytest
from textual.widgets import Button, Input
from textual.worker import WorkerCancelled

from ....application.user_profile.profile_repository import CommittedProfileRepository
from ....application.user_profile.registration import ProfileRegistrationError, register_profile_with_credentials
from ....core.credentials import assess_profile_password
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....domain.user_profile.values import UserProfileFact
from ....entrypoints.tui.components.host import ScreenHostApp
from ....entrypoints.tui.secret.registration import (
    RecoveryHandoverAbandonedError,
    RecoveryHandoverCancelledError,
    RecoveryWordsScreen,
    RegistrationAttempt,
    RegistrationRefusal,
    RegistrationScreen,
)
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

#: Deliberately past the 30s wall-clock bound this handoff no longer carries.
_PAST_REMOVED_BOUND_SECONDS = 33.0
_TERMINAL_SIZE = (140, 60)
_TYPED_PASSWORD = "recovery-words-screen-operator-secret"  # noqa: S105 - synthetic test fixture


def _attempt_registration(
    label: str,
    passphrase: str,
    output_language: str,
    recovery_handover,
) -> RegistrationAttempt:
    """Drive the public registration door through the adapter's injected contract."""
    try:
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            facts=(UserProfileFact(path=PROFILE_OUTPUT_LANGUAGE_PATH, value=output_language),),
            recovery_handover=recovery_handover,
        )
    except RecoveryHandoverCancelledError:
        return RegistrationAttempt(
            expected_refusal=RegistrationRefusal(
                message_key="cli.config.profile.create_recovery_verification_cancelled",
            )
        )
    except RecoveryHandoverAbandonedError:
        return RegistrationAttempt(
            expected_refusal=RegistrationRefusal(
                message_key="cli.config.profile.create_recovery_verification_cancelled",
            )
        )
    except ProfileRegistrationError as refusal:
        if refusal.translated_message is None:
            raise
        return RegistrationAttempt(
            expected_refusal=RegistrationRefusal(
                message_key=refusal.translated_message,
                context=tuple((refusal.context or {}).items()),
            )
        )
    return RegistrationAttempt(outcome=outcome)


def _screen() -> RegistrationScreen:
    return RegistrationScreen(
        assess=assess_profile_password,
        register=_attempt_registration,
        suggested_name="",
    )


async def _fill(pilot, *, username: str, password: str, confirm: str) -> None:
    pilot.app.screen.query_one("#field-username", Input).value = username
    pilot.app.screen.query_one("#field-password", Input).value = password
    pilot.app.screen.query_one("#field-confirm", Input).value = confirm
    await pilot.pause()


async def _wait_for_recovery_screen(pilot) -> RecoveryWordsScreen:
    for _ in range(100):
        if isinstance(pilot.app.screen, RecoveryWordsScreen):
            screen = pilot.app.screen
            if screen.query("#words-value") and screen.query("#btn-confirm-words"):
                return screen
        await pilot.pause(0.1)
    raise AssertionError("recovery confirmation screen did not open")


@pytest.mark.asyncio
async def test_the_full_screen_door_shows_the_words_then_wipes_them(tmp_path) -> None:
    """Creation at the full-screen door enrols recovery and displays it once."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Recovery Words Subject",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")

            # The words screen is now on top; the mnemonic renders there.
            words = await _wait_for_recovery_screen(pilot)
            mnemonic = words.query_one("#words-value")
            rendered = str(mnemonic.render())
            assert len(rendered.split()) == 24
            assert not any(view.label == "Recovery Words Subject" for view in CommittedProfileRepository().list())

            # Confirmation zeroises the container and releases the flow.
            words.query_one("#field-recovery-verification", Input).value = rendered
            await pilot.click("#btn-confirm-words")
            await pilot.app.workers.wait_for_complete()
            for _ in range(100):
                if app.outcome is not None:
                    break
                await pilot.pause(0.05)

        assert app.outcome is not None
        assert app.outcome.label == "Recovery Words Subject"


@pytest.mark.asyncio
async def test_cancelling_recovery_confirmation_publishes_no_capsule(tmp_path) -> None:
    """A displayed phrase is not enrollment until the operator confirms it."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Cancelled Recovery Subject",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")
            await _wait_for_recovery_screen(pilot)

            await pilot.click("#btn-cancel-words")
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()

        assert app.outcome is None
        assert not any(view.label == "Cancelled Recovery Subject" for view in CommittedProfileRepository().list())


@pytest.mark.asyncio
async def test_wrong_recovery_reentry_publishes_no_capsule(tmp_path) -> None:
    """The masked control proves the exact ordered phrase, not button intent."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
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
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()

        assert app.outcome is None
        assert not any(view.label == "Wrong Recovery Reentry" for view in CommittedProfileRepository().list())


@pytest.mark.asyncio
async def test_a_confirmation_past_the_removed_wall_clock_bound_still_publishes(tmp_path) -> None:
    """An operator copying down 24 words is not a failure, however long they take.

    The handoff used to block on ``resolved.wait(timeout=30.0)`` and treat a
    False return as cancellation, so a confirmation arriving after that bound
    was refused and the capsule was never published. Under concurrent load the
    bound was reachable without any operator hesitation at all, which is why
    the parametrised cases failed non-deterministically while passing in
    isolation.

    The wait is now bounded by message-loop liveness rather than elapsed time,
    so this deliberately waits PAST the removed bound before confirming. That
    delay is the whole point of the test: a shorter one passes against the old
    defect too and would prove nothing. Do not shorten it, and do not replace
    the real wait with a patched clock -- the property under test is that no
    wall-clock deadline governs this handoff at all.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Unhurried Recovery Subject",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")
            words = await _wait_for_recovery_screen(pilot)
            rendered = str(words.query_one("#words-value").render())

            deadline = monotonic() + _PAST_REMOVED_BOUND_SECONDS
            while monotonic() < deadline:
                await pilot.pause(0.5)
            assert not any(
                view.label == "Unhurried Recovery Subject" for view in CommittedProfileRepository().list()
            ), "nothing may publish while the operator has not yet confirmed"

            words.query_one("#field-recovery-verification", Input).value = rendered
            await pilot.click("#btn-confirm-words")
            await pilot.app.workers.wait_for_complete()
            for _ in range(100):
                if app.outcome is not None:
                    break
                await pilot.pause(0.05)

        assert app.outcome is not None, "a late but live confirmation must still publish"
        assert app.outcome.label == "Unhurried Recovery Subject"


@pytest.mark.asyncio
async def test_app_shutdown_releases_pending_handoff_without_publication(tmp_path) -> None:
    """Stopping the message loop cannot strand the registration worker."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Shutdown Recovery Subject",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")
            await _wait_for_recovery_screen(pilot)
            pilot.app.exit(None)
            with pytest.raises(WorkerCancelled):
                await pilot.app.workers.wait_for_complete()
        assert not any(view.label == "Shutdown Recovery Subject" for view in CommittedProfileRepository().list())


@pytest.mark.asyncio
async def test_a_words_screen_that_leaves_without_answering_refuses_instead_of_waiting(tmp_path) -> None:
    """An unanswerable handoff must end the attempt, not outlive the process.

    Every other release path keys on something the screen or the app DOES:
    the words screen's own unmount refuses, the registration screen's unmount
    drains its pending handoffs, and the wait gives up once the app stops.
    None of them fire when the screen simply leaves the stack while still
    mounted and the app keeps running -- and a worker blocked on an event
    nobody can set waits for the lifetime of the process, with no error and
    no diagnostic to say why the registration never finished.

    The state is INDUCED rather than simulated: nothing is stubbed and no
    guard is disabled. The screen is removed from the application's own stack
    exactly as a defect would leave it -- off the stack, never unmounted --
    and the assertion is that the attempt ends.

    Removing the stack-membership check in ``_confirm_recovery_possession``
    makes this test hang rather than fail, which is the proof it is the
    guard under test and not the machinery around it.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(
                pilot,
                username="Abandoned Recovery Subject",
                password=_TYPED_PASSWORD,
                confirm=_TYPED_PASSWORD,
            )
            await pilot.click("#btn-create")
            words = await _wait_for_recovery_screen(pilot)

            # Off the stack, still mounted: no unmount fires, so neither the
            # screen's own refusal nor the host's drain releases the handoff.
            # The public ``screen_stack`` property returns a COPY, so removing
            # from it induces nothing; the live list is the private one.
            pilot.app._screen_stack.remove(words)
            assert words.is_mounted

            # The create button is re-enabled only when the attempt settles,
            # which is also the signal the operator sees: the door stops
            # spinning and says something.
            deadline = monotonic() + 10.0
            while app.query_one("#btn-create", Button).disabled and monotonic() < deadline:
                await pilot.pause(0.05)

            assert not app.query_one("#btn-create", Button).disabled, (
                "the registration worker was still waiting on a handoff nobody could answer"
            )
            assert app.outcome is None

        assert not any(view.label == "Abandoned Recovery Subject" for view in CommittedProfileRepository().list())
