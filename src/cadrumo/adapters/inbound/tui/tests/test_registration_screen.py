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

import pytest
from textual.widgets import Input, Static

from .....adapters.persistence.storage.errors import MasterKeyPassphraseMismatchError
from .....adapters.persistence.storage.master_key import get_master_key_provider
from .....domain.user_profile import UserProfileStatus
from .....tests.secure_sql import isolated_profile_storage_root
from .. import RegistrationApp

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (140, 60)
_TYPED_PASSWORD = "screen-typed-operator-secret"  # noqa: S105 - synthetic test fixture
_TOO_SHORT_PASSWORD = "abc"  # noqa: S105 - synthetic test fixture, deliberately under the floor


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
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = RegistrationApp()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(pilot, username="Screen Subject", password=_TYPED_PASSWORD, confirm=_TYPED_PASSWORD)
            await pilot.click("#btn-create")
            await pilot.pause()

        assert app.outcome is not None
        assert app.outcome.label == "Screen Subject"
        assert app.outcome.status is UserProfileStatus.SETUP_INCOMPLETE

        assert len(get_master_key_provider(passphrase_callback=lambda: _TYPED_PASSWORD).get_master_key()) == 32
        with pytest.raises(MasterKeyPassphraseMismatchError):
            get_master_key_provider(passphrase_callback=lambda: "a-different-secret").get_master_key()


@pytest.mark.asyncio
async def test_mismatched_confirmation_refuses_and_creates_nothing(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = RegistrationApp()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(pilot, username="Mismatch", password=_TYPED_PASSWORD, confirm="something-else-entirely")
            await pilot.click("#btn-create")
            await pilot.pause()

            assert app.outcome is None, "a mismatch must not create a profile"
            # Emptiness, not wording: that the refusal zone was populated is
            # the screen's decision; which words fill it is locale data.
            assert str(app.query_one("#registration-refusal", Static).content), "the refusal must be shown"
            app.exit(None)

        assert not list(storage_root.glob("*/manifest.json"))


@pytest.mark.asyncio
async def test_short_password_refuses_and_creates_nothing(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        app = RegistrationApp()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _fill(pilot, username="Short", password=_TOO_SHORT_PASSWORD, confirm=_TOO_SHORT_PASSWORD)
            await pilot.click("#btn-create")
            await pilot.pause()

            assert app.outcome is None
            app.exit(None)

        assert not list(storage_root.glob("*/manifest.json"))


@pytest.mark.asyncio
async def test_blank_username_refuses_and_focuses_the_field(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = RegistrationApp()
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
        app = RegistrationApp()
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
        app = RegistrationApp()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            assert app.query_one("#field-password", Input).password is True
            assert app.query_one("#field-confirm", Input).password is True
            assert app.query_one("#field-username", Input).password is False
            await pilot.pause()
            app.exit(None)
