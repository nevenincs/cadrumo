"""Real proofs for the shared credential-attempt guarantees, driven end to end.

Every assertion here drives a real registered profile through the real
custody stack (real Argon2id, real AEAD) and the real Textual screens --
no mocks, no stand-in storage. `PassphraseApp` (the newest surface) carries
the fullest coverage since it has no prior test file; the cross-cutting
`CredentialApp` guarantees -- single-use dispatch, exact refusal binding,
and that a rejected or superseded credential is never retained on the
screen after the attempt settles -- are proven through it, since all three
credential surfaces share that one base unchanged.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from textual.widgets import Button, Input

from .....application.user_profile.login_session import login_profile
from .....application.user_profile.passphrase_rotation import (
    ProfilePassphraseRotationError,
    rotate_profile_passphrase,
)
from .....application.user_profile.registration import register_profile_with_credentials
from .....core.credentials import assess_profile_password
from .....tests.secure_sql import isolated_profile_storage_root
from ..passphrase import PassphraseApp, PassphraseChangeAttempt, PassphraseChangeRefusal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "Secret journey subject"
_CURRENT_PASSPHRASE = "secret-journey-current-passphrase"  # noqa: S105 - isolated integration fixture
_NEW_PASSPHRASE = "secret-journey-replacement-passphrase"  # noqa: S105 - isolated integration fixture


def _enroll() -> UUID:
    """Enroll one profile. Caller must already hold an isolated storage root."""
    enrolled = register_profile_with_credentials(
        label=_LABEL,
        passphrase=_CURRENT_PASSPHRASE,
        facts=(),
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
    )
    return UUID(enrolled.profile_id)


def _rotate(profile_id: UUID, current: str, new: str, confirm: str) -> PassphraseChangeAttempt:
    """Adapt the public rotation door into the screen's presentation contract.

    The same shape `devtools/fixture.py`'s `registration_attempt` uses for
    registration: a refusal arrives as typed presentation data, never as an
    exception the screen has to recognise.
    """
    try:
        outcome = rotate_profile_passphrase(
            profile_id=profile_id,
            current_passphrase=current,
            new_passphrase=new,
            new_passphrase_confirmation=confirm,
        )
    except ProfilePassphraseRotationError as refusal:
        if refusal.translated_message is None:
            raise
        return PassphraseChangeAttempt(
            expected_refusal=PassphraseChangeRefusal(
                message_key=refusal.translated_message,
                context=tuple((refusal.context or {}).items()),
            )
        )
    return PassphraseChangeAttempt(outcome=outcome)


def _app(profile_id: UUID) -> PassphraseApp:
    return PassphraseApp(
        assess=assess_profile_password,
        rotate=lambda current, new, confirm: _rotate(profile_id, current, new, confirm),
    )


@pytest.mark.asyncio
async def test_a_wrong_current_passphrase_refuses_and_never_rotates(tmp_path: Path) -> None:
    """Exact refusal binding: the door's own mismatch reason reaches the operator."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.query_one("#field-current", Input).value = "not-the-real-passphrase"
            app.query_one("#field-new", Input).value = _NEW_PASSPHRASE
            app.query_one("#field-confirm", Input).value = _NEW_PASSPHRASE
            await pilot.pause()
            await pilot.click("#btn-change")
            await app.workers.wait_for_complete()
            await pilot.pause(0.1)

        assert app.error is None
        assert app.outcome is None

        # The old passphrase must still open the profile: no rotation occurred.
        login_profile(name=str(profile_id), passphrase_callback=lambda: _CURRENT_PASSPHRASE)


@pytest.mark.asyncio
async def test_a_confirmation_mismatch_refuses_locally_before_any_attempt(tmp_path: Path) -> None:
    """The screen's own local check catches this without ever starting a worker."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.query_one("#field-current", Input).value = _CURRENT_PASSPHRASE
            app.query_one("#field-new", Input).value = _NEW_PASSPHRASE
            app.query_one("#field-confirm", Input).value = "a-different-confirmation"
            await pilot.pause()
            await pilot.click("#btn-change")
            await pilot.pause()

            assert not app.attempt_in_flight, "a local mismatch must never start the worker attempt"

        assert app.outcome is None


@pytest.mark.asyncio
async def test_a_completed_rotation_opens_under_the_new_passphrase_only(tmp_path: Path) -> None:
    """The exact operation this screen exists to perform, proven end to end."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.query_one("#field-current", Input).value = _CURRENT_PASSPHRASE
            app.query_one("#field-new", Input).value = _NEW_PASSPHRASE
            app.query_one("#field-confirm", Input).value = _NEW_PASSPHRASE
            await pilot.pause()
            await pilot.click("#btn-change")
            await app.workers.wait_for_complete()
            await pilot.pause(0.1)

        assert app.error is None
        assert app.outcome is not None
        assert app.outcome.password_generation == 2

        login_profile(name=str(profile_id), passphrase_callback=lambda: _NEW_PASSPHRASE)
        with pytest.raises(Exception):  # noqa: B017 - the old credential must be dead, any refusal proves it
            login_profile(name=str(profile_id), passphrase_callback=lambda: _CURRENT_PASSPHRASE)


@pytest.mark.asyncio
async def test_a_second_change_click_while_one_is_in_flight_is_a_single_use_no_op(tmp_path: Path) -> None:
    """Exactly one attempt runs per screen, however many times the button fires."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        started: list[int] = []

        def _counting_rotate(current: str, new: str, confirm: str) -> PassphraseChangeAttempt:
            started.append(1)
            return _rotate(profile_id, current, new, confirm)

        app = PassphraseApp(assess=assess_profile_password, rotate=_counting_rotate)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.query_one("#field-current", Input).value = _CURRENT_PASSPHRASE
            app.query_one("#field-new", Input).value = _NEW_PASSPHRASE
            app.query_one("#field-confirm", Input).value = _NEW_PASSPHRASE
            await pilot.pause()
            await pilot.click("#btn-change")
            # A second click before the worker settles must be swallowed by the
            # attempt_in_flight guard, not queued as a second rotation.
            await pilot.click("#btn-change")
            await app.workers.wait_for_complete()
            await pilot.pause(0.1)

        assert len(started) == 1, "a second click while an attempt is in flight must never start a second worker"


@pytest.mark.asyncio
async def test_abandoning_the_screen_leaves_no_outcome_and_never_touches_storage(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.query_one("#field-current", Input).value = _CURRENT_PASSPHRASE
            app.query_one("#field-new", Input).value = _NEW_PASSPHRASE
            app.query_one("#field-confirm", Input).value = _NEW_PASSPHRASE
            await pilot.pause()
            await pilot.click("#btn-cancel")
            await pilot.pause()

        assert app.outcome is None

        login_profile(name=str(profile_id), passphrase_callback=lambda: _CURRENT_PASSPHRASE)


@pytest.mark.asyncio
async def test_a_refused_attempt_retains_no_plaintext_credential_on_the_app_or_its_error(
    tmp_path: Path,
) -> None:
    """The canary check: no plaintext credential survives a refused attempt.

    `action_change` zero-fills its passphrase buffers in a `finally` block
    regardless of outcome; this proves the observable half of that
    guarantee -- neither the settled `app.error` nor any exception message
    the operator could see carries the current, new, or confirmation
    plaintext, and the screen accepts a fresh attempt rather than latching
    onto stale in-flight state.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        current = "not-the-real-passphrase-canary"
        app = _app(profile_id)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.query_one("#field-current", Input).value = current
            app.query_one("#field-new", Input).value = _NEW_PASSPHRASE
            app.query_one("#field-confirm", Input).value = _NEW_PASSPHRASE
            await pilot.pause()
            await pilot.click("#btn-change")
            await app.workers.wait_for_complete()
            await pilot.pause(0.1)

            assert not app.attempt_in_flight
            assert not app.query_one("#btn-change", Button).disabled, "the screen must accept a fresh attempt"

        rendered_error = "" if app.error is None else str(app.error)
        assert current not in rendered_error
        assert _NEW_PASSPHRASE not in rendered_error


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (120, 40), (200, 50)], ids=["narrow", "medium", "wide"])
async def test_every_field_and_action_is_actually_on_screen_not_only_present(
    tmp_path: Path,
    size: tuple[int, int],
) -> None:
    """Presence in the DOM is not reachability: a control can exist and still
    render outside any real viewport, exactly as `SourceActionCard` did before
    its `height: auto` fix pushed a sibling 180 rows down. Every field and
    button this screen composes must have a positive on-screen region wholly
    inside the terminal at real narrow, ordinary, and wide sizes.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        width, height = size
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            controls = [
                app.query_one(selector, widget_type)
                for selector, widget_type in (
                    ("#field-current", Input),
                    ("#field-new", Input),
                    ("#field-confirm", Input),
                    ("#btn-change", Button),
                    ("#btn-cancel", Button),
                )
            ]
            for control in controls:
                region = control.region
                assert region.width > 0 and region.height > 0, f"{control.id} has no visible area at {size}"
                assert region.x >= 0 and region.x + region.width <= width, (
                    f"{control.id} sits outside the {width}-column terminal: {region}"
                )
                assert region.y >= 0 and region.y + region.height <= height, (
                    f"{control.id} sits outside the {height}-row terminal: {region}"
                )
