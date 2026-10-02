"""Runtime login controls preserve selection and refuse local corrections.

Native authentication and handoff ownership have separate runtime acceptance;
these Pilot proofs exercise controls without opening local custody.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from textual.widgets import Button, Input, Select

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.login_interaction import ProfileLoginChoice
from ..components.host import ScreenHostApp
from ..components.status import PinnedStatusBar
from ..secret.runtime_login import RuntimeLoginMethod, RuntimeLoginScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _choices() -> tuple[ProfileLoginChoice, ProfileLoginChoice]:
    return (
        ProfileLoginChoice(profile_id=str(uuid4()), label="First profile"),
        ProfileLoginChoice(profile_id=str(uuid4()), label="Second profile"),
    )


class _OpeningDetector:
    """Record opener use even when the screen maps its typed refusal."""

    def __init__(self) -> None:
        self.opened: list[UUID] = []

    async def __call__(self, profile_id: UUID) -> RuntimeFrontendClient:
        self.opened.append(profile_id)
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


@pytest.mark.asyncio
async def test_empty_password_refuses_without_opening_a_connection() -> None:
    opener = _OpeningDetector()
    screen = RuntimeLoginScreen(choices=_choices(), open_client=opener, accept_handoff=lambda _: False)
    host = ScreenHostApp(screen)
    async with host.run_test(size=(140, 60)) as pilot:
        await pilot.pause()
        await pilot.click("#runtime-login-submit")
        await pilot.pause()
        assert host.return_value is None
        assert screen.is_mounted
        status = screen.query_one("#runtime-login-status", PinnedStatusBar)
        assert status.tone == "error" and status.message
        assert not screen.query_one("#runtime-login-submit", Button).disabled
        assert opener.opened == []


@pytest.mark.asyncio
async def test_password_is_masked_and_method_change_erases_the_old_proof() -> None:
    opener = _OpeningDetector()
    screen = RuntimeLoginScreen(choices=_choices(), open_client=opener, accept_handoff=lambda _: False)
    async with ScreenHostApp(screen).run_test(size=(140, 60)) as pilot:
        await pilot.pause()
        field = screen.query_one("#runtime-login-credential", Input)
        assert field.password
        assert screen.query_one("#runtime-login-method", Select).value is RuntimeLoginMethod.PASSWORD
        field.value = "synthetic-unused-password"
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_KEY
        await pilot.pause()
        assert field.value == ""
        assert field.password
        assert opener.opened == []


@pytest.mark.asyncio
async def test_profile_chooser_routes_current_selection_to_the_runtime_opener() -> None:
    choices = _choices()
    opened: list[UUID] = []

    async def open_client(profile_id: UUID) -> RuntimeFrontendClient:
        opened.append(profile_id)
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    screen = RuntimeLoginScreen(
        choices=choices, preselected=choices[0].profile_id, open_client=open_client, accept_handoff=lambda _: False
    )
    host = ScreenHostApp(screen)
    async with host.run_test(size=(140, 60)) as pilot:
        await pilot.pause()
        selection = screen.query_one("#runtime-login-profile", Select)
        assert selection.value == choices[0].profile_id
        selection.value = choices[1].profile_id
        await pilot.pause()
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "synthetic-runtime-proof"
        await pilot.click("#runtime-login-submit")
        await host.workers.wait_for_complete()
        await pilot.pause()
        assert opened == [UUID(choices[1].profile_id)]
        assert field.value == ""
        assert screen.is_mounted and host.return_value is None
        assert screen.query_one("#runtime-login-status", PinnedStatusBar).tone == "error"
        assert not screen.query_one("#runtime-login-submit", Button).disabled


@pytest.mark.asyncio
@pytest.mark.parametrize("gesture", ["button", "escape"])
async def test_cancel_discards_unused_password_without_opening_a_connection(gesture: str) -> None:
    opener = _OpeningDetector()
    screen = RuntimeLoginScreen(choices=_choices(), open_client=opener, accept_handoff=lambda _: False)
    host = ScreenHostApp(screen)
    async with host.run_test(size=(140, 60)) as pilot:
        await pilot.pause()
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "synthetic-unused-password"
        if gesture == "button":
            await pilot.click("#runtime-login-cancel")
        else:
            await pilot.press("escape")
        await pilot.pause()
        assert screen not in host.screen_stack
        assert host.return_value is None
        assert field.value == ""
        assert opener.opened == []


@pytest.mark.asyncio
async def test_external_host_exit_erases_unused_input_handles_without_opening_a_connection() -> None:
    opener = _OpeningDetector()
    screen = RuntimeLoginScreen(choices=_choices(), open_client=opener, accept_handoff=lambda _: False)
    host = ScreenHostApp(screen)
    async with host.run_test(size=(140, 60)) as pilot:
        await pilot.pause()
        credential = screen.query_one("#runtime-login-credential", Input)
        reference = screen.query_one("#runtime-login-reference", Input)
        resume_password = screen.query_one("#runtime-login-resume-password", Input)
        credential.value = "synthetic-unused-password"
        reference.value = str(uuid4())
        resume_password.value = "synthetic-unused-recovery-password"
        assert all(field.value for field in (credential, reference, resume_password))
        host.exit(None)
    assert all(field.value == "" for field in (credential, reference, resume_password))
    assert opener.opened == []
    assert host.return_value is None


def test_screen_with_no_profiles_refuses_to_open() -> None:
    with pytest.raises(ValueError, match="requires a profile choice"):
        RuntimeLoginScreen(choices=(), open_client=_OpeningDetector(), accept_handoff=lambda _: False)
