"""The acts that are the person's own in Cadrumo, which an agent never takes.

An agent works inside the one profile the person signed in to, or one the
person issued a key for. Inside it, every registered operation is open to it
as to the command line. Five kinds of act are not agent operations, because
taking one would let an agent authenticate, handle a secret, reach outside
its profile or disclose the profile's data in the person's name:

- an operation whose contract requires a secret, which only the person types;
- the administration of access to the profile: requesting, approving,
  declining, scoping, renewing, rotating and listing its automation keys;
- the runtime requests that sign in, sign out, lock, list or deny sessions,
  reset or change a password, enrol or use recovery, delete a profile, or do
  installation work that belongs to no single profile;
- the consent to send a stored document off this machine to a hosted model,
  which an operation's request carries as its acknowledgement. An agent may
  ask for the same operation's reading that stays on this machine;
- setting, removing or resetting a model provider's credential, which only
  the person manages; reading the masked status stays open to an agent.

This module names them, and names the person's frontends, the only ones that
take one. It refuses nothing itself: the MCP harness offers no tool that sends
one, and the runtime refuses each on every other frontend.

Operations are named by definition id text. This package owns no feature
package's constants, and importing them would invert the dependency.
"""

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

PROVIDER_CREDENTIAL_OPERATIONS: Final = frozenset(
    {
        "provider-settings.remove",
        "provider-settings.reset",
        "provider-settings.set",
    }
)
"""The registered operations that change a model provider's stored credential, by definition id.

Removing and resetting carry no secret, so the secret rule alone would leave them to an agent.
"""


def operation_is_persons_act(definition_id: str, *, ephemeral_secret_required: bool) -> bool:
    """Tell whether a registered operation is the person's own act and not an agent operation."""
    return (
        ephemeral_secret_required
        or definition_id in ACCESS_ADMINISTRATION_OPERATIONS
        or definition_id in PROVIDER_CREDENTIAL_OPERATIONS
    )


PERSONS_FRONTENDS: Final = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
"""The frontends a person works in, and the only ones on which a person's act is taken.

Every other frontend is an agent's, including one added later: it reaches no
person's act until it is named here.
"""


def is_persons_frontend(frontend: OperationFrontendProjection) -> bool:
    """Tell whether ``frontend`` is one the person works in, where the person's own acts are open."""
    return frontend in PERSONS_FRONTENDS


__all__ = [
    "ACCESS_ADMINISTRATION_OPERATIONS",
    "PERSONS_FRONTENDS",
    "PROVIDER_CREDENTIAL_OPERATIONS",
    "is_persons_frontend",
    "operation_is_persons_act",
]
