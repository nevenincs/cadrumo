"""TUI bootstrap composition over the canonical Login screen."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from textual.widgets import Select

from ....application.user_profile.login_interaction import ProfileLoginAttempt
from ....application.user_profile.login_session import ProfileLoginOutcome
from ....application.user_profile.workbench_bootstrap import (
    WorkbenchBootstrapInventoryState,
    WorkbenchBootstrapSessionState,
    WorkbenchBootstrapV1,
    WorkbenchRegistrationRequiredV1,
)
from ..bootstrap import handoff_registration_required, run_workbench_bootstrap, workbench_login_screen
from ..components.host import ScreenHostApp
from ..secret.login import LoginScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "11111111-1111-4111-8111-111111111111"
_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)


def _login_required() -> WorkbenchBootstrapV1:
    from ....application.user_profile.login_interaction import ProfileLoginChoice

    return WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
        session_state=WorkbenchBootstrapSessionState.LOGIN_REQUIRED,
        choices=(ProfileLoginChoice(profile_id=_PROFILE, label="Operator"),),
        preselected_profile_id=_PROFILE,
    )


def _authenticated_outcome() -> ProfileLoginOutcome:
    return ProfileLoginOutcome(
        bucket_id=_PROFILE,
        label="Operator",
        authenticated_at=_NOW,
        idle_deadline=_NOW + timedelta(minutes=30),
        absolute_deadline=_NOW + timedelta(hours=8),
        session_persisted=False,
        already_authenticated=False,
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


def test_coordinator_routes_resumed_custody_without_opening_login() -> None:
    resumed = WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
        session_state=WorkbenchBootstrapSessionState.RESUMED,
        choices=_login_required().choices,
        preselected_profile_id=_PROFILE,
        selected_profile_id=_PROFILE,
        selected_profile_label="Operator",
    )
    authenticated: list[WorkbenchBootstrapV1] = []

    result = run_workbench_bootstrap(
        prepare=lambda: resumed,
        run_login=lambda _screen: pytest.fail("resumed custody must not reopen login"),
        registration_door=lambda _requirement: pytest.fail("resumed custody must not register"),
        authenticated_door=authenticated.append,
        cancelled_door=lambda _state: pytest.fail("resumed custody must not cancel"),
        degraded_door=lambda _state: pytest.fail("resumed custody must not degrade"),
    )

    assert result is resumed
    assert authenticated == [resumed]


def test_coordinator_routes_login_cancellation_without_authenticating() -> None:
    cancelled: list[WorkbenchBootstrapV1] = []
    screens: list[LoginScreen] = []

    result = run_workbench_bootstrap(
        prepare=_login_required,
        run_login=lambda screen: screens.append(screen) and None,
        registration_door=lambda _requirement: pytest.fail("recognized inventory must not register"),
        authenticated_door=lambda _state: pytest.fail("cancelled login must not authenticate"),
        cancelled_door=cancelled.append,
        degraded_door=lambda _state: pytest.fail("recognized inventory must not degrade"),
    )

    assert result.session_state is WorkbenchBootstrapSessionState.CANCELLED
    assert cancelled == [result]
    assert len(screens) == 1


def test_coordinator_routes_real_login_outcome_to_authenticated_host() -> None:
    authenticated: list[WorkbenchBootstrapV1] = []
    screens: list[LoginScreen] = []

    def run_login(screen: LoginScreen) -> ProfileLoginOutcome:
        screens.append(screen)
        return _authenticated_outcome()

    result = run_workbench_bootstrap(
        prepare=_login_required,
        run_login=run_login,
        registration_door=lambda _requirement: pytest.fail("recognized inventory must not register"),
        authenticated_door=authenticated.append,
        cancelled_door=lambda _state: pytest.fail("authenticated login must not cancel"),
        degraded_door=lambda _state: pytest.fail("recognized inventory must not degrade"),
    )

    assert result.session_state is WorkbenchBootstrapSessionState.AUTHENTICATED
    assert result.selected_profile_id == _PROFILE
    assert authenticated == [result]
    assert len(screens) == 1


def test_coordinator_routes_degraded_inventory_without_opening_login() -> None:
    degraded = WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.DEGRADED,
        reason_code="workbench.bootstrap.profile_inventory_unavailable",
    )
    observed: list[WorkbenchBootstrapV1] = []

    result = run_workbench_bootstrap(
        prepare=lambda: degraded,
        run_login=lambda _screen: pytest.fail("degraded inventory must not open login"),
        registration_door=lambda _requirement: pytest.fail("degraded inventory must not register"),
        authenticated_door=lambda _state: pytest.fail("degraded inventory must not authenticate"),
        cancelled_door=lambda _state: pytest.fail("degraded inventory must not cancel"),
        degraded_door=observed.append,
    )

    assert result is degraded
    assert observed == [degraded]


def test_coordinator_hands_empty_inventory_to_registration_once() -> None:
    empty = WorkbenchBootstrapV1(inventory_state=WorkbenchBootstrapInventoryState.EMPTY)
    requirements: list[WorkbenchRegistrationRequiredV1] = []

    result = run_workbench_bootstrap(
        prepare=lambda: empty,
        run_login=lambda _screen: pytest.fail("empty inventory must not open login"),
        registration_door=requirements.append,
        authenticated_door=lambda _state: pytest.fail("empty inventory must not authenticate"),
        cancelled_door=lambda _state: pytest.fail("empty inventory must not cancel"),
        degraded_door=lambda _state: pytest.fail("empty inventory must not degrade"),
    )

    assert result is empty
    assert requirements == [WorkbenchRegistrationRequiredV1()]
