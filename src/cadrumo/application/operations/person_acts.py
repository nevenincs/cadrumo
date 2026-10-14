"""Registered person-only acts and authenticated human frontend identities."""

from __future__ import annotations

from typing import Final

from .registry import OperationFrontendProjection

ACCESS_ADMINISTRATION_OPERATIONS: Final = frozenset(
    {
        "user-profile.automation-approve",
        "user-profile.automation-decline",
        "user-profile.automation-inventory",
        "user-profile.automation-renew",
        "user-profile.automation-request",
        "user-profile.automation-rotate",
        "user-profile.automation-scope",
    }
)
"""The registered operations that administer who may reach the profile, by definition id."""


def operation_is_persons_act(definition_id: str, *, ephemeral_secret_required: bool) -> bool:
    """Tell whether a registered operation is the person's own act and not an delegated client operation."""
    return ephemeral_secret_required or definition_id in ACCESS_ADMINISTRATION_OPERATIONS


PERSONS_FRONTENDS: Final = frozenset(
    {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.DESKTOP}
)
"""The frontends a person works in, and the only ones on which a person's act is taken.

Every other frontend is an delegated client's, including one added later: it reaches no
person's act until it is named here.
"""


def is_persons_frontend(frontend: OperationFrontendProjection) -> bool:
    """Tell whether ``frontend`` is one the person works in, where the person's own acts are open."""
    return frontend in PERSONS_FRONTENDS


__all__ = [
    "ACCESS_ADMINISTRATION_OPERATIONS",
    "PERSONS_FRONTENDS",
    "is_persons_frontend",
    "operation_is_persons_act",
]
