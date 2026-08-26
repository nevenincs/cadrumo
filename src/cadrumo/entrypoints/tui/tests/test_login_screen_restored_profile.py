"""Full-screen login behavior for a restore-fed profile.

Two routes the earlier Pilot suite left uncodified: a profile that reaches
the machine through the capsule restore door (rather than registration)
must present on the login screen and unlock through the real door.

No mocks. Real registration, real restore, real Argon2id, the real
LoginApp through Textual's headless Pilot.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input

from ....application.user_profile.capsule_restore import restore_profile_from_source_with_password
from ....application.user_profile.login_interaction import (
    ProfileLoginChoice,
    attempt_profile_login,
    profile_login_choices,
)
from ....application.user_profile.login_session import logout_active_profile
from ....application.user_profile.registration import register_profile_with_credentials
from ....entrypoints.tui.secret.app import LoginApp
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (140, 60)
_PASSWORD = "login-restored-operator-secret"  # noqa: S105 - synthetic test fixture


def _screen(choices: list[ProfileLoginChoice]) -> LoginApp:
    return LoginApp(choices=choices, authenticate=attempt_profile_login)


async def _unlock_with(pilot, password: str) -> None:
    pilot.app.query_one("#field-passphrase", Input).value = password
    await pilot.pause()
    await pilot.click("#btn-unlock")
    await pilot.app.workers.wait_for_complete()


@pytest.mark.asyncio
async def test_a_restored_profile_presents_and_unlocks_on_the_login_screen(
    tmp_path: Path,
) -> None:
    """A profile that arrives by restore (not registration) is a login citizen."""

    with isolated_profile_storage_root(tmp_path=tmp_path / "source-root") as source_root:
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Restore-born",
            passphrase=_PASSWORD,
        )
        capsule = source_root / "buckets" / outcome.profile_id
        restored = restore_profile_from_source_with_password(
            label="Restore-born",
            source=capsule,
            password=_PASSWORD,
            root=tmp_path / "tui-root",
        )

    from ....core.config import override_settings

    with override_settings(cadrumo_local_storage_root=str(tmp_path / "tui-root")):
        choices = list(profile_login_choices())
        assert any(choice.profile_id == restored.profile_id for choice in choices)
        logout_active_profile()

        app = _screen(choices)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await _unlock_with(pilot, _PASSWORD)
            assert app.error is None
            assert app.outcome is not None
            assert app.outcome.bucket_id == restored.profile_id
