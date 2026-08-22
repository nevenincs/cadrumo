"""Pilot-driven proofs for the credential-first first screen.

Every test drives the real :class:`RegistrationApp` through Textual's
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
"""

from __future__ import annotations

from uuid import UUID

import pytest
from textual.widgets import Input, Static

from .....adapters.persistence.storage.custody import (
    ProfileCustodyPasswordError,
    load_committed_profile_password_material,
    unlock_profile_custody,
)
from .....core import ProfilePasswordRefusalReason, assess_profile_password
from .....core.i18n import tr
from .....entrypoints.cli._config._manager_frontend import attempt_registration
from .....tests.secure_sql import isolated_profile_storage_root
from .. import RegistrationApp
from .._registration_screen import assessment_refusal
from .._status_bar import PinnedStatusBar

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (140, 60)
_TYPED_PASSWORD = "screen-typed-operator-secret"  # noqa: S105 - synthetic test fixture


@pytest.mark.parametrize(
    ("candidate", "reason", "message_key"),
    (
        ("a" * 14, ProfilePasswordRefusalReason.TOO_FEW_SCALARS, "profile_password_too_few_scalars"),
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
def test_submission_refusals_stay_typed_secret_free_and_create_nothing(
    tmp_path,
    candidate: str,
    reason: ProfilePasswordRefusalReason,
    message_key: str,
) -> None:
    """Direct attempts cover candidates Textual widgets cannot transport."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        attempt = attempt_registration("Refused candidate", candidate, "en")

        assert attempt.outcome is None
        assert attempt.expected_refusal is not None
        assert attempt.expected_refusal == assessment_refusal(assess_profile_password(candidate))
        assert attempt.expected_refusal.message_key.endswith(message_key)
        assert dict(attempt.expected_refusal.context)["reason"] == reason.value
        assert candidate not in repr(attempt)
        assert "INTERNAL" not in repr(attempt)
        assert not list(storage_root.glob("*/manifest.json"))


def _screen(**kwargs) -> RegistrationApp:
    """Build the screen wired to the doors the CLI actually gives it.

    The production composition rather than a stand-in, so these tests
    exercise the same path an operator does: a stub here would prove the
    widgets talk to a stub.
    """
    return RegistrationApp(assess=assess_profile_password, register=attempt_registration, **kwargs)


async def _fill(pilot, *, username: str, password: str, confirm: str) -> None:
    """Type into the three real Input widgets, as an operator would."""
    app = pilot.app
    app.query_one("#field-username", Input).value = username
    app.query_one("#field-password", Input).value = password
    app.query_one("#field-confirm", Input).value = confirm
    await pilot.pause()


@pytest.mark.asyncio
async def test_typing_credentials_and_pressing_create_makes_a_live_profile(tmp_path) -> None:
    """The screen creates a real, unlocked profile from a name and a password.

    The bucket is then challenged with the typed password and with a wrong
    one, through real Argon2id derivation and a real AEAD unwrap, so this
    proves the screen wired the operator's credential through to the key
    material rather than merely reporting success.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(pilot, username="Screen Subject", password=_TYPED_PASSWORD, confirm=_TYPED_PASSWORD)
            await pilot.click("#btn-create")
            # Registration runs on a worker thread, so a bare pause only
            # yields the event loop and may return before the profile
            # exists; joining the worker is what makes this deterministic.
            await app.workers.wait_for_complete()
            await pilot.pause()

        assert app.outcome is not None
        assert app.outcome.label == "Screen Subject"
        assert app.outcome.setup_state.value == "incomplete"

        # The password typed into the screen is the one that opens the
        # profile. Asserted against the committed capsule rather than a
        # process-wide key store: custody is per profile, so "the typed
        # password unlocks THIS profile" is the property that matters.
        material = load_committed_profile_password_material(
            UUID(str(app.outcome.profile_id)),
            root=storage_root,
        )
        unlocked = unlock_profile_custody(
            password=_TYPED_PASSWORD,
            envelope=material.envelope,
            sentinel=material.sentinel,
        )
        assert len(bytes(unlocked.dek)) == 32
        with pytest.raises(ProfileCustodyPasswordError):
            unlock_profile_custody(
                password="a-different-secret",  # noqa: S106 - synthetic wrong password under test
                envelope=material.envelope,
                sentinel=material.sentinel,
            )


@pytest.mark.asyncio
async def test_mismatched_confirmation_refuses_and_creates_nothing(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(pilot, username="Mismatch", password=_TYPED_PASSWORD, confirm="something-else-entirely")
            await pilot.click("#btn-create")
            await pilot.pause()

            assert app.outcome is None, "a mismatch must not create a profile"
            # Emptiness, not wording: that the refusal zone was populated is
            # the screen's decision; which words fill it is locale data.
            status = app.query_one("#credential-status", PinnedStatusBar)
            assert status.tone == "error"
            assert status.message, "the refusal must be shown in the pinned channel"
            app.exit(None)

        assert not list(storage_root.glob("*/manifest.json"))


@pytest.mark.asyncio
async def test_original_fourteen_scalar_failure_is_typed_without_internal_diagnostics(tmp_path) -> None:
    candidate = "a" * 14
    assert len(candidate) == 14
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(pilot, username="Short", password=candidate, confirm=candidate)
            strength = app.query_one("#strength-line", Static)
            live_rendered = str(strength.render())
            assert live_rendered
            assert candidate not in live_rendered
            assert "INTERNAL" not in live_rendered.upper()
            assert "profile password must contain 15 to 256 Unicode scalars" not in live_rendered
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
            assert "profile password must contain 15 to 256 Unicode scalars" not in rendered
            assert "Traceback" not in rendered
            app.exit(None)

        assert not list(storage_root.glob("*/manifest.json"))


@pytest.mark.asyncio
async def test_unkeyed_unexpected_registration_failure_keeps_internal_classification(tmp_path) -> None:
    fault = RuntimeError("synthetic registration transport failure")

    def fail_registration(_label: str, _password: str, _language: str):
        raise fault

    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = RegistrationApp(assess=assess_profile_password, register=fail_registration)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(pilot, username="Unexpected", password=_TYPED_PASSWORD, confirm=_TYPED_PASSWORD)
            await pilot.click("#btn-create")
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert app.error is fault
            status = app.query_one("#credential-status", PinnedStatusBar)
            assert status.tone == "error"
            assert status.message
            assert status.message == tr("errors.internal.internal_cli_unexpected_boundary")
            app.exit(None)


@pytest.mark.asyncio
async def test_blank_username_refuses_and_focuses_the_field(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(pilot, username="   ", password=_TYPED_PASSWORD, confirm=_TYPED_PASSWORD)
            await pilot.click("#btn-create")
            await pilot.pause()

            assert app.outcome is None
            assert app.focused is app.query_one("#field-username", Input)
            app.exit(None)


@pytest.mark.asyncio
async def test_the_strength_line_tracks_the_password_field(tmp_path) -> None:
    """The advisory band updates while typing and clears when emptied.

    Asserted through the CSS class rather than the rendered words: the
    words are locale data, the class is the screen's own decision.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
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
            app.exit(None)


@pytest.mark.asyncio
async def test_the_password_fields_are_masked(tmp_path) -> None:
    """Both secret fields render masked; the name field does not.

    A screen that collects a credential in clear text on a shared terminal
    is the failure this pins.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            assert app.query_one("#field-password", Input).password is True
            assert app.query_one("#field-confirm", Input).password is True
            assert app.query_one("#field-username", Input).password is False
            await pilot.pause()
            app.exit(None)
