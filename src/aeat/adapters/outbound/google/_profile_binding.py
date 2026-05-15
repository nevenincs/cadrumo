"""Active-profile resolver for the Google OAuth Desktop integration.

Every `aeat config google ...` command and every secure-store read or
write the OAuth flow performs is scoped to a single AEAT profile.
This module exposes one entry point — `resolve_active_profile` —
that the CLI surface and the secure-store accessors call to obtain
that profile name. The resolver honours an explicit `--profile`
override when given and otherwise falls back to the workflow state's
`active_profile` field.

There is no global Google session, no shared cross-profile token, and
no multi-account binding within a single profile. The whole-package
contract is enforced at this single chokepoint.
"""

from __future__ import annotations

from ....application.workflow._persistence import workflow_state_repository
from ._errors import GoogleAuthProfileUnboundError


def resolve_active_profile(profile_override: str | None = None) -> str:
    """Return the AEAT profile name backing this Google OAuth call.

    Args:
        profile_override: Optional CLI `--profile` value. When non-empty
            this wins over workflow state, so a CLI invocation like
            `aeat config google login --profile business` reaches the
            right per-profile records even if a different profile is
            currently active.

    Returns:
        The resolved AEAT profile name. Always a non-empty string.

    Raises:
        GoogleAuthProfileUnboundError: When `profile_override` is empty
            or `None` and `workflow_state_repository().load().active_profile`
            is also `None`. The error carries a `suggestion` pointing to
            `aeat config init` and a `context` payload naming the
            resolution attempt for renderers.
    """

    override = (profile_override or "").strip()
    if override:
        return override

    state = workflow_state_repository().load()
    if state.active_profile is not None and state.active_profile.strip():
        return state.active_profile.strip()

    raise GoogleAuthProfileUnboundError(
        "no active AEAT profile bound and no --profile override given",
        context={"override": profile_override or "", "active_profile": state.active_profile or ""},
        suggestion="aeat config init --tax-id <NIF>",
    )


__all__ = ["resolve_active_profile"]
