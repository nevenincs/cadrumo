"""Full-screen login behavior for a restore-fed profile.

Two routes the earlier Pilot suite left uncodified: a profile that reaches
the machine through the capsule restore door (rather than registration)
must present on the login screen and unlock through the real door.

No mocks. Real registration, real restore, real Argon2id, the real
LoginScreen through Textual's headless Pilot.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input

from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.capsule_restore import (
    read_profile_capsule_source,
    restore_profile_capsule_with_password,
)
from ....application.user_profile.login_interaction import (
    ProfileLoginChoice,
    attempt_profile_login,
    profile_login_choices,
)
from ....application.user_profile.login_session import logout_active_profile
from ....application.user_profile.registration import register_profile_with_credentials
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ....entrypoints.tui.components.host import ScreenHostApp
from ....entrypoints.tui.secret.login import LoginScreen

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (140, 60)
_CREDENTIAL_INPUT = "login-restored-operator-secret"


def _screen(choices: list[ProfileLoginChoice], *, profile_decode_context: ProfileDecodeContext) -> LoginScreen:
    def _authenticate(profile_id: str, passphrase: str):
        return attempt_profile_login(
            profile_id,
            passphrase,
            profile_decode_context=profile_decode_context,
        )

    return LoginScreen(choices=choices, authenticate=_authenticate)


async def _unlock_with(pilot, password: str) -> None:
    pilot.app.screen.query_one("#field-passphrase", Input).value = password
    await pilot.pause()
    await pilot.click("#btn-unlock")
    await pilot.app.workers.wait_for_complete()


@pytest.mark.asyncio
async def test_a_restored_profile_presents_and_unlocks_on_the_login_screen(
    tmp_path: Path,
) -> None:
    """A profile that arrives by restore (not registration) is a login citizen."""

    with isolated_profile_storage_root(tmp_path=tmp_path / "source-root") as source_root:
        # Registration validates facts against registry authority, so it runs under a real lease.
        with bundled_indexed_authority().operation():
            profile_create_context, profile_decode_context = _profile_contexts_for_test()
            outcome = register_profile_with_credentials(
                label="Restore-born",
                passphrase=_CREDENTIAL_INPUT,
                profile_create_context=profile_create_context,
                profile_decode_context=profile_decode_context,
            )
        capsule = source_root / "buckets" / outcome.profile_id
        restored = restore_profile_capsule_with_password(
            label="Restore-born",
            capsule=read_profile_capsule_source(capsule),
            password=_CREDENTIAL_INPUT,
            root=tmp_path / "tui-root",
            profile_decode_context=profile_decode_context,
        )

    from ....core.config import override_settings

    with override_settings(cadrumo_local_storage_root=str(tmp_path / "tui-root")):
        choices = list(profile_login_choices())
        assert any(choice.profile_id == restored.profile_id for choice in choices)
        logout_active_profile()

        app = _screen(choices, profile_decode_context=profile_decode_context)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await _unlock_with(pilot, _CREDENTIAL_INPUT)
            assert app.error is None
            assert app.outcome is not None
            assert app.outcome.bucket_id == restored.profile_id
