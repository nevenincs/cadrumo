"""Pilot-driven proofs for the full-screen way back in.

Every test drives the real :class:`LoginApp` through Textual's headless
Pilot, against a real storage root holding a profile created through the
real registration path, and unlocks it through the real application login
door — real Argon2id derivation, a real AEAD unwrap, a real minted
session. A stand-in anywhere on that chain would prove only that widgets
talk to a stand-in, and the property under test here is precisely that
the operator's keystrokes reach key material.

Assertions are against widget ids, typed outcomes, and persisted state,
never against rendered prose: the prose is locale data, and asserting it
from the same catalogue the screen reads would be tautological.
"""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Button, Input, Select

from ....application.user_profile.login_interaction import ProfileLoginChoice, attempt_profile_login
from ....application.user_profile.login_session import login_profile, logout_active_profile
from ....application.user_profile.registration import register_profile_with_credentials
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.secret.login import LoginApp
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (140, 60)
_PASSWORD = "login-screen-operator-secret"  # noqa: S105 - synthetic test fixture
"""One password for every fixture profile, because the master key is
storage-root-wide: profiles in one root are unwrapped by one passphrase,
so a per-profile password is not a state this application can be in."""

_WRONG_PASSWORD = "not-the-password-that-was-chosen"  # noqa: S105 - synthetic test fixture

_BACKOFF_WAIT_SECONDS = 2.5
"""Long enough to outlast the backoff one failed attempt arms.

The schedule is ``min(2 ** failures, 60)`` seconds, so a single failure
imposes two. Waited in real time rather than cleared through the throttle
authority: what is being proved is that an operator who mistypes can get
back in on the same screen, and stepping past the control they would
actually meet would prove something weaker."""


def _register(label: str) -> str:
    """Create one real profile through the real door and return its id."""
    outcome = register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        label=label,
        passphrase=_PASSWORD,
    )
    # Registration leaves the new profile unlocked. The screen under test
    # exists for a LOCKED machine, so the session is closed again here;
    # otherwise the idempotent-login guard would return the already-open
    # session and no unwrap would be exercised at all.
    logout_active_profile()
    return outcome.bucket_id


def _screen(choices: list[ProfileLoginChoice], *, preselected: str | None = None) -> LoginApp:
    """The production composition, wired to the application interaction contract."""
    return LoginApp(choices=choices, authenticate=attempt_profile_login, preselected=preselected)


async def _unlock_with(pilot, password: str) -> None:
    """Type a password and press the button, as an operator does."""
    pilot.app.query_one("#field-passphrase", Input).value = password
    await pilot.pause()
    await pilot.click("#btn-unlock")
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_typing_the_password_and_pressing_log_in_opens_a_real_session(tmp_path) -> None:
    """The screen unlocks a real profile and mints a real session.

    The claim is end to end: the profile was created by the real create
    path, the screen hands the typed password to the real login door, and
    what comes back is the typed session outcome naming the profile that
    was picked. Nothing on that chain is stood in for.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register("Login Subject")

        app = _screen([ProfileLoginChoice(profile_id=profile_id, label="Login Subject")])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _unlock_with(pilot, _PASSWORD)

        assert app.error is None
        assert app.outcome is not None, "the typed password must open the profile"
        assert app.outcome.bucket_id == profile_id
        assert app.outcome.label == "Login Subject"
        assert app.outcome.already_authenticated is False, "a logged-out profile must be authenticated, not resumed"
        assert app.outcome.absolute_deadline > app.outcome.authenticated_at, "a real session carries a real window"


@pytest.mark.asyncio
async def test_a_wrong_password_refuses_in_place_without_leaving(tmp_path) -> None:
    """A typo is answered on the page, not by returning to the shell.

    Four things are pinned together, because a screen could satisfy any
    one of them alone and still be wrong: no session was opened, the
    refusal is visible, the rejected text is gone from the field, and the
    screen is still running with its button live.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register("Refusal Subject")

        app = _screen([ProfileLoginChoice(profile_id=profile_id, label="Refusal Subject")])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _unlock_with(pilot, _WRONG_PASSWORD)

            assert app.outcome is None, "a wrong password must not open anything"
            assert app.is_running, "the screen must stay open so the operator can retry"
            # Emptiness, not wording: that the refusal zone was populated
            # is the screen's decision; which words fill it is locale data.
            status = app.query_one("#credential-status", PinnedStatusBar)
            assert status.tone == "error"
            assert status.message, "the refusal must be shown in the pinned channel"
            assert app.query_one("#field-passphrase", Input).value == "", (
                "the rejected password must be cleared, or the retry appends to the mistake"
            )
            assert app.query_one("#btn-unlock", Button).disabled is False, "the operator must be able to try again"

            # The immediate retry meets the backoff one failure arms, and
            # meets it HERE rather than as a traceback: the screen shows
            # the wait and stays open. Asserted because it is what the
            # operator actually experiences after a typo.
            await _unlock_with(pilot, _PASSWORD)
            assert app.outcome is None, "the backoff must hold the immediate retry"
            assert app.is_running, "a throttled retry must refuse in place, not close the screen"
            assert status.tone == "error"
            assert status.message

            app.exit(None)


@pytest.mark.asyncio
async def test_the_operator_can_retry_on_the_same_screen_once_the_backoff_clears(tmp_path) -> None:
    """A mistyped password costs a wait, not the screen.

    This is the property a refusal that merely *looked* survivable would
    miss: after the backoff passes, the same still-open screen unlocks
    the profile, so the worker handle was released and the frozen inputs
    were thawed rather than left disabled behind a visible error line.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register("Retry Subject")

        app = _screen([ProfileLoginChoice(profile_id=profile_id, label="Retry Subject")])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _unlock_with(pilot, _WRONG_PASSWORD)
            assert app.outcome is None

            await asyncio.sleep(_BACKOFF_WAIT_SECONDS)
            await _unlock_with(pilot, _PASSWORD)

        assert app.error is None
        assert app.outcome is not None, "the retry on the same screen must succeed once the wait is served"
        assert app.outcome.bucket_id == profile_id


@pytest.mark.asyncio
async def test_the_chosen_profile_is_the_one_that_opens(tmp_path) -> None:
    """The chooser decides which profile is opened.

    One password unwraps every profile in a storage root, so the
    discriminating fact is not whether *a* profile opens — one always
    would — but WHICH one the outcome names. Moving off the preselected
    first row is what makes a screen that quietly used the pointer, the
    preselection, or row zero fail here.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        first = _register("Alpha Subject")
        second = _register("Beta Subject")

        app = _screen(
            [
                ProfileLoginChoice(profile_id=first, label="Alpha Subject"),
                ProfileLoginChoice(profile_id=second, label="Beta Subject"),
            ],
            preselected=first,
        )
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            assert app.selected_profile_id() == first, "the preselection must be what the chooser opens on"

            app.query_one("#field-profile", Select).value = second
            await pilot.pause()
            assert app.selected_profile_id() == second, "the chooser must hold the operator's pick"
            await _unlock_with(pilot, _PASSWORD)

        assert app.error is None
        assert app.outcome is not None
        assert app.outcome.bucket_id == second, "the profile the chooser was left on is the one that must open"
        assert app.outcome.label == "Beta Subject"


@pytest.mark.asyncio
async def test_the_password_field_is_masked(tmp_path) -> None:
    """The secret renders masked; a screen that showed it on a shared terminal is the failure."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register("Masked Subject")

        app = _screen([ProfileLoginChoice(profile_id=profile_id, label="Masked Subject")])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            assert app.query_one("#field-passphrase", Input).password is True
            await pilot.pause()
            app.exit(None)


@pytest.mark.asyncio
async def test_an_empty_password_refuses_without_calling_the_door(tmp_path) -> None:
    """Pressing log in with nothing typed refuses locally and opens nothing."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register("Empty Subject")

        app = _screen([ProfileLoginChoice(profile_id=profile_id, label="Empty Subject")])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.click("#btn-unlock")
            await pilot.pause()

            assert app.outcome is None
            assert app.is_running, "a blank submission is a correction, not an exit"
            status = app.query_one("#credential-status", PinnedStatusBar)
            assert status.tone == "error"
            assert status.message
            app.exit(None)


@pytest.mark.asyncio
async def test_cancelling_leaves_without_opening_anything(tmp_path) -> None:
    """Cancel closes the screen with no outcome and no session.

    The profile must still be locked afterwards, which is checked by
    logging in normally and seeing a fresh authentication rather than the
    idempotent resume a still-open session would produce.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register("Cancel Subject")

        app = _screen([ProfileLoginChoice(profile_id=profile_id, label="Cancel Subject")])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            app.query_one("#field-passphrase", Input).value = _PASSWORD
            await pilot.pause()
            await pilot.click("#btn-cancel")
            await pilot.pause()

        assert app.error is None
        assert app.outcome is None, "cancelling must not report a login"

        resumed = login_profile(name=profile_id, passphrase_callback=lambda: _PASSWORD)
        assert resumed.already_authenticated is False, "cancelling must have left the profile locked"


@pytest.mark.asyncio
async def test_a_screen_with_no_profiles_refuses_to_open() -> None:
    """A chooser with no rows is not a page; the caller is told so up front.

    The CLI seam never builds one, but the screen refuses rather than
    rendering an empty chooser the operator cannot act on or escape into
    a useful state.
    """
    with pytest.raises(ValueError, match="at least one profile"):
        _screen([])
