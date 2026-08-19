"""The full-screen login on a restore-fed profile, and legacy refusal.

Two routes the earlier Pilot suite left uncodified: a profile that reaches
the machine through the capsule restore door (rather than registration)
must present on the login screen and unlock through the real door; and a
storage root carrying a retired custody member must refuse at the login
surface instead of offering profiles it cannot attest.

No mocks. Real registration, real restore, real Argon2id, the real
LoginApp through Textual's headless Pilot.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input

from .....adapters.persistence.storage.custody import ProfileCustodyRefusedError
from .....application.user_profile import (
    logout_active_profile,
    register_profile_with_credentials,
    restore_profile_from_source_with_password,
)
from .....entrypoints.cli._config._login_frontend import attempt_login
from .....tests.secure_sql import isolated_profile_storage_root
from .. import LoginApp, LoginChoice

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (140, 60)
_PASSWORD = "login-restored-operator-secret"  # noqa: S105 - synthetic test fixture


def _screen(choices: list[LoginChoice]) -> LoginApp:
    return LoginApp(choices=choices, authenticate=attempt_login)


async def _unlock_with(pilot, password: str) -> None:
    pilot.app.query_one("#field-passphrase", Input).value = password
    await pilot.pause()
    await pilot.click("#btn-unlock")
    await pilot.app.workers.wait_for_complete()


def _login_choices() -> list[LoginChoice]:
    from .....application.workflow import list_profile_buckets

    return [
        LoginChoice(profile_id=pointer.bucket_id, label=pointer.label)
        for pointer in sorted(list_profile_buckets().values(), key=lambda pointer: pointer.label.casefold())
    ]


@pytest.mark.asyncio
async def test_a_restored_profile_presents_and_unlocks_on_the_login_screen(
    tmp_path: Path,
) -> None:
    """A profile that arrives by restore (not registration) is a login citizen."""

    with isolated_profile_storage_root(tmp_path=tmp_path / "source-root") as source_root:
        outcome = register_profile_with_credentials(label="Restore-born", passphrase=_PASSWORD)
        capsule = source_root / "buckets" / outcome.profile_id
        restored = restore_profile_from_source_with_password(
            label="Restore-born",
            source=capsule,
            password=_PASSWORD,
            root=tmp_path / "tui-root",
        )

    from .....core.config import override_settings

    with override_settings(cadrumo_local_storage_root=str(tmp_path / "tui-root")):
        choices = _login_choices()
        assert any(choice.profile_id == restored.profile_id for choice in choices)
        logout_active_profile()

        app = _screen(choices)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _unlock_with(pilot, _PASSWORD)
            assert app.error is None
            assert app.outcome is not None
            assert app.outcome.bucket_id == restored.profile_id


@pytest.mark.asyncio
async def test_a_legacy_custody_member_refuses_at_the_login_surface(
    tmp_path: Path,
) -> None:
    """A retired plaintext manifest in the root refuses instead of lying."""
    with isolated_profile_storage_root(tmp_path=tmp_path / "legacy-root") as root:
        (root / "buckets").mkdir(parents=True, exist_ok=True)
        (root / "buckets" / "11111111-1111-4111-8111-111111111111" / "manifest.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (root / "buckets" / "11111111-1111-4111-8111-111111111111" / "manifest.toml").write_text(
            "bucket_id = '11111111-1111-4111-8111-111111111111'\n",
            encoding="utf-8",
        )
        with pytest.raises(ProfileCustodyRefusedError):
            _login_choices()
