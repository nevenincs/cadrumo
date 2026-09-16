"""Pilot-driven proofs for the credential-first first screen.

Every test drives the real :class:`RegistrationScreen` through Textual's
headless Pilot and, where a profile is actually created, against a real
storage root with real key derivation. Assertions are against widget ids,
typed outcomes, and persisted state — never rendered prose, which is
locale data and would make the assertion tautological.

The load-bearing test is
:func:`test_typing_credentials_and_pressing_create_makes_a_live_profile`:
it types into the real widgets, clicks the real button, and then proves
the profile exists and its bucket answers to the typed password. That is
the whole paradigm shift in one path — a name and a password, and the
profile is real.

Recovery is the optional follow-up. The tests under "recovery offer" drive
the real enrolment door through the offer and code screens and read the
result off the capsule on disk: skipping and cancelling install nothing,
and only a confirmed code installs the wrapper.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
from textual.css.query import NoMatches
from textual.widgets import Button, Input, Static

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)

from ....adapters.persistence.storage.custody.recovery import PROFILE_CUSTODY_RECOVERY_FILENAME
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.login_interaction import attempt_profile_login
from ....application.user_profile.login_session import logout_active_profile
from ....application.user_profile.recovery_custody import profile_recovery_status
from ....core.credentials import ProfilePasswordRefusalReason, assess_profile_password
from ....core.i18n.render import tr
from ....entrypoints.tui.components.host import ScreenHostApp
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.secret.credentials import assessment_refusal
from ....entrypoints.tui.secret.registration import RecoveryCodeScreen, RecoveryOfferScreen, RegistrationScreen
from .fixture import recovery_enrollment_attempt, registration_attempt

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (140, 60)
_TYPED_INPUT = "screen-typed-operator-secret"


def _storage_entries(storage_root: Path) -> tuple[Path, ...]:
    """Snapshot storage atomically enough for isolation teardown on Windows."""
    try:
        return tuple(storage_root.iterdir())
    except FileNotFoundError:
        return ()


def _recovery_envelopes(storage_root: Path) -> tuple[Path, ...]:
    """Every installed recovery wrapper under the isolated root, wherever its capsule lives."""
    return tuple(sorted(storage_root.rglob(PROFILE_CUSTODY_RECOVERY_FILENAME)))


async def _wait_until(pilot, condition: Callable[[], bool], *, polls: int = 300, interval: float = 0.1) -> bool:
    """Pause the pilot until ``condition`` holds or the poll budget is spent.

    Creation and enrolment both run real key derivation on a worker thread,
    so the screens they push arrive after an amount of time this test does
    not own; the budget is generous and the return value is asserted by the
    caller so a stalled path reads as a failure rather than a hang.
    """
    for _ in range(polls):
        if condition():
            return True
        await pilot.pause(interval)
    return condition()


async def _wait_for_screen(pilot, screen_type: type, *, composed: str) -> bool:
    """Wait for ``screen_type`` to be active AND for ``composed`` to be laid out on it.

    A pushed screen is active before its ``compose`` has run, and a composed
    widget has no place on screen until the next layout pass. A click sent
    in either window lands on nothing and presses nothing, so the widget
    having a non-empty region is what proves the screen can be driven.
    """

    def laid_out() -> bool:
        screen = pilot.app.screen
        if not isinstance(screen, screen_type):
            return False
        try:
            area: int = screen.query(composed).first().region.area
        except NoMatches:
            return False
        return area > 0

    return await _wait_until(pilot, laid_out)


async def _displayed_recovery_code(pilot) -> str:
    """The code the RecoveryCodeScreen shows, once it has actually rendered."""
    code: str = ""

    def _rendered() -> bool:
        nonlocal code
        try:
            code = str(pilot.app.screen.query_one("#code-value", Static).content)
        except NoMatches:
            return False
        return bool(code)

    assert await _wait_until(pilot, _rendered), "the recovery code never rendered"
    return code


@pytest.mark.parametrize(
    ("candidate", "reason", "message_key"),
    (
        ("a" * 257, ProfilePasswordRefusalReason.TOO_MANY_SCALARS, "profile_password_too_many_scalars"),
        (
            "😀" * 255 + "abcde",
            ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES,
            "profile_password_too_many_utf8_bytes",
        ),
        ("a" * 15 + "\ud800", ProfilePasswordRefusalReason.CONTAINS_SURROGATE, "profile_password_contains_surrogate"),
        ("a" * 15 + "\udc00", ProfilePasswordRefusalReason.CONTAINS_SURROGATE, "profile_password_contains_surrogate"),
    ),
)
@pytest.mark.asyncio
async def test_live_submission_refusals_stay_typed_secret_free_and_create_nothing(
    tmp_path,
    candidate: str,
    reason: ProfilePasswordRefusalReason,
    message_key: str,
) -> None:
    """Every non-short invalid boundary traverses the real Textual screen."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen()
        expected = assessment_refusal(assess_profile_password(candidate))
        assert expected is not None
        assert expected.translated_message.endswith(message_key)
        assert dict(expected.context)["reason"] == reason.value
        exact_message = tr(expected.translated_message, **dict(expected.context))

        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(app, pilot, username="Refused candidate", password=candidate, confirm=candidate)
            live_rendered = str(app.query_one("#strength-line", Static).render())
            assert live_rendered == exact_message
            await pilot.click("#btn-create")
            await pilot.pause()

            status = app.query_one("#credential-status", PinnedStatusBar)
            assert app.outcome is None
            assert app.error is None
            assert status.tone == "error"
            assert str(status.message) == exact_message
            rendered_surface = live_rendered + str(status.message)
            assert candidate not in rendered_surface
            assert "INTERNAL" not in rendered_surface.upper()
            assert "profile password must contain 8 to 256 Unicode scalars" not in rendered_surface
            assert "Traceback" not in rendered_surface
            pilot.app.exit(None)

        assert _storage_entries(storage_root) == ()


def _screen(**kwargs) -> RegistrationScreen:
    """Build the screen wired to the doors the CLI actually gives it.

    The production composition rather than a stand-in, so these tests
    exercise the same path an operator does: a stub here would prove the
    widgets talk to a stub. Without ``enroll_recovery`` the screen is the
    passphrase-only composition that leaves as soon as the profile exists.
    """
    return RegistrationScreen(assess=assess_profile_password, register=registration_attempt, **kwargs)


async def _fill(screen: RegistrationScreen, pilot, *, username: str, password: str, confirm: str) -> None:
    """Type into the three real Input widgets, as an operator would.

    Addressed against the screen, not the host: the host's own default
    screen carries none of these fields.
    """
    await pilot.pause()
    app = screen
    app.query_one("#field-username", Input).value = username
    app.query_one("#field-password", Input).value = password
    app.query_one("#field-confirm", Input).value = confirm
    await pilot.pause()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidate",
    (
        pytest.param("a" * 15, id="15-scalars"),
        pytest.param("a" * 256, id="256-scalars"),
        pytest.param("😀" * 256, id="1024-bytes"),
        pytest.param("é" * 15, id="composed"),
        pytest.param("é" * 15, id="decomposed"),
    ),
)
async def test_typing_credentials_and_pressing_create_makes_a_live_profile(tmp_path, candidate: str) -> None:
    """The screen creates a real, unlocked profile from a name and a password.

    The bucket is then challenged with the typed password and with a wrong
    one, through real Argon2id derivation and a real AEAD unwrap, so this
    proves the screen wired the operator's credential through to the key
    material rather than merely reporting success.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(app, pilot, username="Screen Subject", password=candidate, confirm=candidate)
            await pilot.click("#btn-create")
            await pilot.app.workers.wait_for_complete()
            # Without an enrolment door there is nothing to offer: the screen
            # leaves the moment the profile exists, and no offer was pushed.
            assert await _host_received(pilot), "the screen must leave as soon as the profile exists"
            assert not isinstance(pilot.app.screen, RecoveryOfferScreen | RecoveryCodeScreen)

        assert app.outcome is not None
        assert pilot.app.return_value is app.outcome
        assert app.outcome.label == "Screen Subject"
        assert app.outcome.setup_state.value == "incomplete"

        # The password typed into the screen is the one that opens this exact
        # profile through the application login door. That door exercises the
        # real Argon2id, sentinel proof, and session publication without making
        # an inbound-surface test depend on persistence-owned record types.
        profile_id = str(app.outcome.profile_id)
        _, profile_decode_context = _profile_contexts_for_test()
        logout_active_profile()
        authenticated = attempt_profile_login(profile_id, candidate, profile_decode_context=profile_decode_context)
        assert authenticated.refusal is None
        assert authenticated.outcome is not None
        assert authenticated.outcome.bucket_id == profile_id
        logout_active_profile()

        counterpart = unicodedata.normalize(
            "NFD" if unicodedata.is_normalized("NFC", candidate) else "NFC",
            candidate,
        )
        wrong_password = counterpart if counterpart != candidate else "a-different-secret"
        refused = attempt_profile_login(profile_id, wrong_password, profile_decode_context=profile_decode_context)
        assert refused.outcome is None
        assert refused.refusal


@pytest.mark.asyncio
async def test_mismatched_confirmation_refuses_and_creates_nothing(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(app, pilot, username="Mismatch", password=_TYPED_INPUT, confirm="something-else-entirely")
            await pilot.click("#btn-create")
            await pilot.pause()

            assert app.outcome is None, "a mismatch must not create a profile"
            # Emptiness, not wording: that the refusal zone was populated is
            # the screen's decision; which words fill it is locale data.
            status = app.query_one("#credential-status", PinnedStatusBar)
            assert status.tone == "error"
            assert status.message, "the refusal must be shown in the pinned channel"
            pilot.app.exit(None)

        assert _storage_entries(storage_root) == ()


@pytest.mark.asyncio
async def test_seven_scalar_failure_is_typed_without_internal_diagnostics(tmp_path) -> None:
    candidate = "a" * 7
    assert len(candidate) == 7
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(app, pilot, username="Short", password=candidate, confirm=candidate)
            strength = app.query_one("#strength-line", Static)
            live_rendered = str(strength.render())
            assert live_rendered
            assert candidate not in live_rendered
            assert "INTERNAL" not in live_rendered.upper()
            assert "profile password must contain 8 to 256 Unicode scalars" not in live_rendered
            await pilot.click("#btn-create")
            await pilot.pause()

            assert app.outcome is None
            assert app.error is None
            status = app.query_one("#credential-status", PinnedStatusBar)
            rendered = str(status.message)
            assert status.tone == "error"
            assert rendered
            assert candidate not in rendered
            assert "INTERNAL" not in rendered.upper()
            assert "profile password must contain 8 to 256 Unicode scalars" not in rendered
            assert "Traceback" not in rendered
            pilot.app.exit(None)

        assert _storage_entries(storage_root) == ()


@pytest.mark.asyncio
async def test_unkeyed_unexpected_registration_failure_keeps_internal_classification(tmp_path) -> None:
    fault = RuntimeError("synthetic registration transport failure")

    def fail_registration(_label: str, _password: str, _language: str):
        raise fault

    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = RegistrationScreen(assess=assess_profile_password, register=fail_registration)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(app, pilot, username="Unexpected", password=_TYPED_INPUT, confirm=_TYPED_INPUT)
            await pilot.click("#btn-create")
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()

            assert app.error is fault
            status = app.query_one("#credential-status", PinnedStatusBar)
            assert status.tone == "error"
            assert status.message
            assert status.message == tr("errors.internal.internal_cli_unexpected_boundary")
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_blank_username_refuses_and_focuses_the_field(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(app, pilot, username="   ", password=_TYPED_INPUT, confirm=_TYPED_INPUT)
            await pilot.click("#btn-create")
            await pilot.pause()

            assert app.outcome is None
            assert app.focused is app.query_one("#field-username", Input)
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_the_strength_line_tracks_the_password_field(tmp_path) -> None:
    """The advisory band updates while typing and clears when emptied.

    Asserted through the CSS class rather than the rendered words: the
    words are locale data, the class is the screen's own decision.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            field = app.query_one("#field-password", Input)
            line = app.query_one("#strength-line", Static)

            field.value = "abc"
            await pilot.pause()
            assert line.has_class("strength-refused")

            field.value = "correct horse battery staple"
            await pilot.pause()
            assert line.has_class("strength-strong")
            assert not line.has_class("strength-refused")

            field.value = ""
            await pilot.pause()
            assert not any(
                line.has_class(name)
                for name in ("strength-refused", "strength-weak", "strength-fair", "strength-strong")
            )
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_the_password_fields_are_masked(tmp_path) -> None:
    """Both secret fields render masked; the name field does not.

    A screen that collects a credential in clear text on a shared terminal
    is the failure this pins.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            assert app.query_one("#field-password", Input).password is True
            assert app.query_one("#field-confirm", Input).password is True
            assert app.query_one("#field-username", Input).password is False
            await pilot.pause()
            pilot.app.exit(None)


# ── recovery offer ──────────────────────────────────────────────────────────


def _screen_with_recovery() -> RegistrationScreen:
    """The installed composition: creation followed by the optional recovery offer."""
    return _screen(enroll_recovery=recovery_enrollment_attempt)


async def _create_and_reach_the_offer(app: RegistrationScreen, pilot, *, username: str) -> None:
    await _fill(app, pilot, username=username, password=_TYPED_INPUT, confirm=_TYPED_INPUT)
    await pilot.click("#btn-create")
    assert await _wait_for_screen(pilot, RecoveryOfferScreen, composed="#btn-skip-recovery"), (
        "creation must be followed by the recovery offer"
    )
    assert app in pilot.app.screen_stack, "the screen must not leave while the offer is still open"
    assert pilot.app.return_value is None, "the host must not receive the profile while the offer is still open"


async def _host_received(pilot) -> bool:
    """Whether the hosted screen has dismissed with its outcome, ending the host."""
    return await _wait_until(pilot, lambda: pilot.app.return_value is not None)


@pytest.mark.asyncio
async def test_skipping_the_recovery_offer_leaves_with_the_profile_and_installs_nothing(tmp_path) -> None:
    """Declining is the default and costs nothing: the profile stays passphrase-only."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen_with_recovery()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _create_and_reach_the_offer(app, pilot, username="Skips Recovery")
            offer = pilot.app.screen
            assert offer.focused is offer.query_one("#btn-skip-recovery", Button), "declining must be the default"
            await pilot.click("#btn-skip-recovery")
            await pilot.app.workers.wait_for_complete()
            assert await _host_received(pilot), "skipping must leave with the created profile"

        assert app.error is None
        assert app.outcome is not None
        assert pilot.app.return_value is app.outcome
        assert app.outcome.label == "Skips Recovery"
        assert _recovery_envelopes(storage_root) == ()
        assert profile_recovery_status(profile_id=UUID(app.outcome.profile_id)).enrolled is False


@pytest.mark.asyncio
async def test_confirming_the_displayed_code_installs_the_recovery_wrapper(tmp_path) -> None:
    """Setting up recovery shows the code once and installs only after it is typed back.

    The code is retyped in lower case without its separators: case and
    grouping are presentation, and an operator copying from paper must not
    be refused over them. Installation is read off the capsule on disk and
    through the application's own status door, not off the screen.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen_with_recovery()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _create_and_reach_the_offer(app, pilot, username="Enrols Recovery")
            await pilot.click("#btn-setup-recovery")
            assert await _wait_for_screen(pilot, RecoveryCodeScreen, composed="#btn-confirm-code"), (
                "setting up must show the code screen"
            )
            assert _recovery_envelopes(storage_root) == (), "nothing is installed before the code is confirmed"

            code = await _displayed_recovery_code(pilot)
            assert "-" in code, "the code is shown grouped for copying"
            pilot.app.screen.query_one("#field-recovery-verification", Input).value = code.replace("-", "").lower()
            status = app.query_one("#credential-status", PinnedStatusBar)
            await pilot.click("#btn-confirm-code")
            await pilot.app.workers.wait_for_complete()
            assert await _host_received(pilot), "a confirmed code must leave with the created profile"
            assert status.tone != "error", f"enrolment was refused: {status.message}"

        assert app.error is None
        assert app.outcome is not None
        assert pilot.app.return_value is app.outcome
        envelopes = _recovery_envelopes(storage_root)
        assert len(envelopes) == 1, f"exactly one wrapper must be installed, found {envelopes}"
        assert envelopes[0].parent.name == "custody"
        assert profile_recovery_status(profile_id=UUID(app.outcome.profile_id)).enrolled is True


@pytest.mark.asyncio
async def test_a_wrong_code_is_refused_in_place_without_installing(tmp_path) -> None:
    """A mistyped confirmation keeps the code screen open and installs nothing."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen_with_recovery()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _create_and_reach_the_offer(app, pilot, username="Mistypes Code")
            status = app.query_one("#credential-status", PinnedStatusBar)
            await pilot.click("#btn-setup-recovery")
            assert await _wait_for_screen(pilot, RecoveryCodeScreen, composed="#btn-confirm-code"), (
                f"setting up must show the code screen; status read {status.tone!r}: {status.message}"
            )
            code = await _displayed_recovery_code(pilot)
            wrong = code[::-1]
            assert wrong != code
            field = pilot.app.screen.query_one("#field-recovery-verification", Input)
            field.value = wrong
            await pilot.click("#btn-confirm-code")
            await pilot.pause()

            assert isinstance(pilot.app.screen, RecoveryCodeScreen), "a mismatch keeps the operator on the code"
            assert field.value == "", "the mistyped proof is cleared, not kept for editing"
            assert pilot.app.return_value is None
            assert _recovery_envelopes(storage_root) == ()

            await pilot.click("#btn-cancel-code")
            await pilot.app.workers.wait_for_complete()
            assert await _host_received(pilot), "cancelling must still leave with the created profile"

        assert app.outcome is not None
        assert pilot.app.return_value is app.outcome
        assert _recovery_envelopes(storage_root) == ()


@pytest.mark.asyncio
async def test_cancelling_on_the_code_screen_installs_nothing_and_still_leaves_with_the_profile(tmp_path) -> None:
    """Backing out after seeing the code is a decline, not a failure."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen_with_recovery()
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _create_and_reach_the_offer(app, pilot, username="Cancels Recovery")
            status = app.query_one("#credential-status", PinnedStatusBar)
            await pilot.click("#btn-setup-recovery")
            assert await _wait_for_screen(pilot, RecoveryCodeScreen, composed="#btn-confirm-code"), (
                f"setting up must show the code screen; status read {status.tone!r}: {status.message}"
            )
            await _displayed_recovery_code(pilot)
            await pilot.click("#btn-cancel-code")
            await pilot.app.workers.wait_for_complete()
            assert await _host_received(pilot), "cancelling must still leave with the created profile"
            assert status.tone != "error", "a deliberate cancel is not a refusal"

        assert app.error is None
        assert app.outcome is not None
        assert pilot.app.return_value is app.outcome
        assert app.outcome.label == "Cancels Recovery"
        assert _recovery_envelopes(storage_root) == ()
        assert profile_recovery_status(profile_id=UUID(app.outcome.profile_id)).enrolled is False
