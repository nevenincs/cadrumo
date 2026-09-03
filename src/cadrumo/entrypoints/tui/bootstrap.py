"""TUI composition over the application-owned workbench bootstrap state."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ...application.user_profile.login_interaction import ProfileLoginAttempt, attempt_profile_login
from ...application.user_profile.login_session import ProfileLoginOutcome
from ...application.user_profile.workbench_bootstrap import (
    WorkbenchBootstrapSessionState,
    WorkbenchBootstrapV1,
    WorkbenchRegistrationRequiredV1,
    complete_workbench_login,
)
from .secret.login import LoginScreen


class WorkbenchRegistrationRequiredDoorV1(Protocol):
    """Host handoff to the existing registration journey."""

    def __call__(self, requirement: WorkbenchRegistrationRequiredV1, /) -> None:
        """Accept the typed zero-profile requirement without inventing a profile."""
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


__all__ = [
    "WorkbenchRegistrationRequiredDoorV1",
    "finish_workbench_login",
    "handoff_registration_required",
    "workbench_login_screen",
]
