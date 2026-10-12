"""The acts that are the person's own in Cadrumo, which an agent never takes.

An agent works inside the one profile the person signed in to, or one the
person issued a key for. Inside it, every registered operation is open to it
as to the command line. Three kinds of act are not agent operations, because
taking one would let an agent authenticate, handle a secret or reach outside
its profile:

- an operation whose contract requires a secret, which only the person types;
- the administration of access to the profile: requesting, approving,
  declining, scoping, renewing, rotating and listing its automation keys;
- the runtime requests that sign in, sign out, lock, list or deny sessions,
  reset or change a password, enrol or use recovery, delete a profile, or do
  installation work that belongs to no single profile.

This module names them. It refuses nothing itself: the MCP harness offers no
tool that sends one, and the runtime refuses each on the MCP frontend.

Operations are named by definition id text. This package owns no feature
package's constants, and importing them would invert the dependency.
"""

from __future__ import annotations

from typing import Final

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

PERSON_RUNTIME_REQUESTS: Final = frozenset(
    {
        "automation_deny",
        "enrollment_inspect",
        "enrollment_poll",
        "enrollment_prepare",
        "enrollment_reconcile",
        "enrollment_submit",
        "human_sign_out",
        "password_reset",
        "password_reset_prepare",
        "profile_delete",
        "profile_delete_prepare",
        "profile_recovery_prepare",
        "profile_resume",
        "session_inventory",
        "session_lock",
        "sign_in_status",
    }
)
"""The requests of the runtime's own door that authenticate or administer sessions, keys or the profile.

Every installation act is the person's act as well: it belongs to no single
profile. A sign-in by password is too; a key the person configured is
presented by the login request of the key method, which is not one of these.
Reading the stored sign-in names no frontend and admits nothing; an agent
reads its own standing from its session instead.
"""


def operation_is_persons_act(definition_id: str, *, ephemeral_secret_required: bool) -> bool:
    """Tell whether a registered operation is the person's own act and not an agent operation."""
    return ephemeral_secret_required or definition_id in ACCESS_ADMINISTRATION_OPERATIONS


__all__ = [
    "ACCESS_ADMINISTRATION_OPERATIONS",
    "PERSON_RUNTIME_REQUESTS",
    "operation_is_persons_act",
]
