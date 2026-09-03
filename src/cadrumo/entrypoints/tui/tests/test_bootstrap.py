"""TUI bootstrap composition over the canonical Login screen."""

from __future__ import annotations

import pytest
from textual.widgets import Select

from ....application.user_profile.login_interaction import ProfileLoginAttempt
from ....application.user_profile.workbench_bootstrap import (
    WorkbenchBootstrapInventoryState,
    WorkbenchBootstrapSessionState,
    WorkbenchBootstrapV1,
    WorkbenchRegistrationRequiredV1,
)
from ..bootstrap import handoff_registration_required, workbench_login_screen
from ..components.host import ScreenHostApp
from ..secret.login import LoginScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "11111111-1111-4111-8111-111111111111"


def _login_required() -> WorkbenchBootstrapV1:
    from ....application.user_profile.login_interaction import ProfileLoginChoice

    return WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
        session_state=WorkbenchBootstrapSessionState.LOGIN_REQUIRED,
        choices=(ProfileLoginChoice(profile_id=_PROFILE, label="Operator"),),
        preselected_profile_id=_PROFILE,
    )


@pytest.mark.asyncio
async def test_login_required_builds_the_real_screen_with_injected_authentication() -> None:
    attempts: list[tuple[str, str]] = []

    def authenticate(profile_id: str, passphrase: str) -> ProfileLoginAttempt:
        attempts.append((profile_id, passphrase))
        return ProfileLoginAttempt(refusal="refused")

    screen = workbench_login_screen(_login_required(), authenticate=authenticate)

    assert isinstance(screen, LoginScreen)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert screen.query_one("#field-profile", Select).value == _PROFILE
        assert attempts == []


def test_empty_inventory_hands_registration_requirement_to_host_once() -> None:
    requirements: list[WorkbenchRegistrationRequiredV1] = []
    preparation = WorkbenchBootstrapV1(inventory_state=WorkbenchBootstrapInventoryState.EMPTY)

    handoff_registration_required(preparation, requirements.append)

    assert requirements == [WorkbenchRegistrationRequiredV1()]
    with pytest.raises(ValueError, match="requires an empty profile inventory"):
        handoff_registration_required(_login_required(), requirements.append)
