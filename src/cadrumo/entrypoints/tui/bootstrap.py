"""TUI composition over the application-owned workbench bootstrap state."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ...application.user_profile.login_interaction import ProfileLoginAttempt, attempt_profile_login
from ...application.user_profile.login_session import ProfileLoginOutcome
from ...application.user_profile.workbench_bootstrap import (
    WorkbenchBootstrapInventoryState,
    WorkbenchBootstrapSessionState,
    WorkbenchBootstrapV1,
    WorkbenchRegistrationRequiredV1,
    complete_workbench_login,
    prepare_workbench_bootstrap,
)
from .secret.login import LoginScreen


class WorkbenchRegistrationRequiredDoorV1(Protocol):
    """Host handoff to the existing registration journey."""

    def __call__(self, requirement: WorkbenchRegistrationRequiredV1, /) -> None:
        """Accept the typed zero-profile requirement without inventing a profile."""
        ...


class WorkbenchBootstrapStateDoorV1(Protocol):
    """Receive one closed, non-secret bootstrap state from the child session."""

    def __call__(self, preparation: WorkbenchBootstrapV1, /) -> None:
        """Handle the state without reopening profile inventory or custody."""
        ...


class WorkbenchLoginScreenRunnerV1(Protocol):
    """Run the real credential screen and return only its non-secret outcome."""

    def __call__(self, screen: LoginScreen, /) -> ProfileLoginOutcome | None:
        """Return ``None`` when the operator cancels the credential screen."""
        ...


def workbench_login_screen(
    preparation: WorkbenchBootstrapV1,
    *,
    authenticate: Callable[[str, str], ProfileLoginAttempt] = attempt_profile_login,
) -> LoginScreen:
    """Build the real Login screen for an application-admitted bootstrap state."""
    if preparation.session_state is not WorkbenchBootstrapSessionState.LOGIN_REQUIRED:
        raise ValueError("workbench login screen requires a login-required bootstrap")
    return LoginScreen(
        choices=preparation.choices,
        authenticate=authenticate,
        preselected=preparation.preselected_profile_id,
    )


def finish_workbench_login(
    preparation: WorkbenchBootstrapV1,
    outcome: ProfileLoginOutcome | None,
) -> WorkbenchBootstrapV1:
    """Return authenticated or cancelled state from the existing screen result."""
    return complete_workbench_login(preparation, outcome)


def handoff_registration_required(
    preparation: WorkbenchBootstrapV1,
    door: WorkbenchRegistrationRequiredDoorV1,
) -> None:
    """Invoke registration ownership exactly once for a genuine empty inventory."""
    requirement = preparation.registration_required
    if requirement is None:
        raise ValueError("registration handoff requires an empty profile inventory")
    door(requirement)


def run_workbench_bootstrap(
    *,
    prepare: Callable[[], WorkbenchBootstrapV1] = prepare_workbench_bootstrap,
    run_login: WorkbenchLoginScreenRunnerV1,
    registration_door: WorkbenchRegistrationRequiredDoorV1,
    authenticated_door: WorkbenchBootstrapStateDoorV1,
    cancelled_door: WorkbenchBootstrapStateDoorV1,
    degraded_door: WorkbenchBootstrapStateDoorV1,
    authenticate: Callable[[str, str], ProfileLoginAttempt] = attempt_profile_login,
) -> WorkbenchBootstrapV1:
    """Drive one child session from inventory through a closed safe outcome.

    This coordinator owns no profile record, session key, recovery material, or
    registration implementation.  It makes exactly one inventory observation,
    then routes that immutable observation to its owner: an already-resumed
    session reaches the authenticated host, an empty store reaches the existing
    registration journey, a degraded observation is surfaced as such, and only
    a recognized non-resumed inventory opens the real Login screen.
    """
    preparation = prepare()
    if preparation.inventory_state in {
        WorkbenchBootstrapInventoryState.CONCURRENT_CHANGE,
        WorkbenchBootstrapInventoryState.DEGRADED,
    }:
        degraded_door(preparation)
        return preparation
    if preparation.registration_required is not None:
        handoff_registration_required(preparation, registration_door)
        return preparation
    if preparation.session_state is WorkbenchBootstrapSessionState.RESUMED:
        authenticated_door(preparation)
        return preparation
    if preparation.session_state is not WorkbenchBootstrapSessionState.LOGIN_REQUIRED:
        raise ValueError("workbench bootstrap reached an unsupported session state")

    completed = finish_workbench_login(
        preparation,
        run_login(workbench_login_screen(preparation, authenticate=authenticate)),
    )
    if completed.session_state is WorkbenchBootstrapSessionState.AUTHENTICATED:
        authenticated_door(completed)
    elif completed.session_state is WorkbenchBootstrapSessionState.CANCELLED:
        cancelled_door(completed)
    else:
        raise ValueError("workbench login completion reached an unsupported session state")
    return completed


__all__ = [
    "WorkbenchBootstrapStateDoorV1",
    "WorkbenchLoginScreenRunnerV1",
    "WorkbenchRegistrationRequiredDoorV1",
    "finish_workbench_login",
    "handoff_registration_required",
    "run_workbench_bootstrap",
    "workbench_login_screen",
]
