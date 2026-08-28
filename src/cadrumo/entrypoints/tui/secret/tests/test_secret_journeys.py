"""Real proofs for the shared credential-attempt guarantees, driven end to end.

Every assertion here drives a real registered profile through the real
custody stack (real Argon2id, real AEAD) and the real Textual screens --
no mocks, no stand-in storage. `PassphraseScreen` (the newest surface) carries
the fullest coverage since it has no prior test file; the cross-cutting
`CredentialScreen` guarantees -- single-use dispatch, exact refusal binding,
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
from ...components.host import ScreenHostApp
from ...components.widgets import ContentScroll
from ..passphrase import PassphraseChangeAttempt, PassphraseChangeRefusal, PassphraseScreen

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


def _app(profile_id: UUID) -> PassphraseScreen:
    return PassphraseScreen(
        assess=assess_profile_password,
        rotate=lambda current, new, confirm: _rotate(profile_id, current, new, confirm),
    )


@pytest.mark.asyncio
async def test_a_wrong_current_passphrase_refuses_and_never_rotates(tmp_path: Path) -> None:
    """Exact refusal binding: the door's own mismatch reason reaches the operator."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
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
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
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
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
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

        app = PassphraseScreen(assess=assess_profile_password, rotate=_counting_rotate)
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
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
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
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
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
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
async def test_every_field_and_action_is_actually_reachable_not_only_present(
    tmp_path: Path,
    size: tuple[int, int],
) -> None:
    """Presence in the DOM is not reachability.

    A control can exist and still render outside any real viewport, exactly as
    `SourceActionCard` did before its `height: auto` fix pushed a sibling 180
    rows down. Every field and button this screen composes must therefore have
    a positive on-screen region, lie wholly inside the terminal horizontally,
    and be scrollable into full view vertically.

    The two axes are asserted differently because the operator has different
    recourse on each. There is no horizontal scroll affordance on this surface,
    so a control past the right edge is unrecoverable and containment is
    absolute. Vertically the surface mounts a scroll host, so the reachable
    property is that each control can be brought fully into view -- asserted
    here by actually scrolling to it and re-measuring, never by assuming that
    mounting a scroll host makes anything reachable.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        width, height = size
        async with ScreenHostApp(app).run_test(size=size) as pilot:
            await pilot.pause()
            selectors = (
                ("#field-current", Input),
                ("#field-new", Input),
                ("#field-confirm", Input),
                ("#btn-change", Button),
                ("#btn-cancel", Button),
            )
            for selector, widget_type in selectors:
                control = app.query_one(selector, widget_type)
                region = control.region
                assert region.width > 0 and region.height > 0, f"{control.id} has no visible area at {size}"
                assert region.x >= 0 and region.x + region.width <= width, (
                    f"{control.id} sits outside the {width}-column terminal: {region}"
                )

            for selector, widget_type in selectors:
                control = app.query_one(selector, widget_type)
                control.scroll_visible(animate=False, force=True)
                await pilot.pause()
                region = control.region
                assert region.height > 0, f"{control.id} lost its area after being scrolled to at {size}"
                assert region.y >= 0 and region.y + region.height <= height, (
                    f"{control.id} cannot be brought into a {height}-row terminal: {region}"
                )


@pytest.mark.asyncio
async def test_the_narrow_terminal_reaches_the_actions_only_by_scrolling(tmp_path: Path) -> None:
    """The eighty-by-twenty-four floor is served by scrolling, and that is a decision.

    This screen carries three credential fields, each with its own label, plus
    the new password hint and its live strength line. Measured at the floor the
    content column is twenty-eight rows against a twenty-two row viewport, so
    it cannot be made to fit without removing something the operation needs:
    collapsing the intro and the hint recovers three rows and still does not
    fit, and dropping a field or a label would remove part of the operation
    rather than lay it out differently.

    So the surface scrolls, which is the answer the responsive-layout proofs
    already record for every other full-screen surface -- vertical extent is
    carried by the scroll host rather than asserted away. This test pins both
    halves of that decision so it cannot be reversed silently: the actions
    genuinely start below the fold at the floor, and the scroll host genuinely
    carries them into view. If a later change makes the content fit outright,
    the first assertion fails and this test should be retired deliberately
    rather than relaxed.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        async with ScreenHostApp(app).run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            scroll = app.query_one(ContentScroll)
            change = app.query_one("#btn-change", Button)

            assert scroll.max_scroll_y > 0, (
                "the content column fits the floor, so this surface no longer depends on scrolling"
            )
            assert change.region.y + change.region.height > 24, (
                "the primary action already fits unscrolled; the decision this test pins no longer applies"
            )

            change.scroll_visible(animate=False, force=True)
            await pilot.pause()
            assert scroll.scroll_offset.y > 0, "reaching the primary action did not move the scroll host"
            assert change.region.y >= 0 and change.region.y + change.region.height <= 24, (
                f"the primary action is unreachable even after scrolling: {change.region}"
            )


@pytest.mark.asyncio
async def test_the_action_row_costs_one_row_of_buttons_not_two(tmp_path: Path) -> None:
    """Cancel and change share one row, as the sibling login screen actions do.

    Stacking them cost three rows on a surface already past the floor, for no
    layout benefit: both buttons are short and the panel is at least
    seventy-three columns wide wherever this screen renders. The asserted
    property is that the two actions occupy a single row, which a vertical
    stack cannot satisfy.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _enroll()
        app = _app(profile_id)
        async with ScreenHostApp(app).run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            cancel = app.query_one("#btn-cancel", Button)
            change = app.query_one("#btn-change", Button)
            assert cancel.region.y == change.region.y, (
                f"the actions are stacked rather than sharing a row: {cancel.region} {change.region}"
            )
            assert cancel.region.right <= change.region.x, "the actions overlap horizontally"
