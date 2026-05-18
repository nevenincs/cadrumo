"""Active-profile resolver for the Google OAuth Desktop integration.

Every `aeat config google ...` command and every secure-store read or
write the OAuth flow performs is scoped to a single AEAT profile.
This module exposes one entry point — `resolve_active_profile` —
that the CLI surface and the secure-store accessors call to obtain
that profile name. The resolver honours an explicit `--profile`
override when given and otherwise reads the active-profile
precedence chain in `application/workflow/_models.resolve_active_bucket_id`
(Settings override > plaintext pointer file).

There is no global Google session, no shared cross-profile token, and
no multi-account binding within a single profile. The whole-package
contract is enforced at this single chokepoint.
"""

from __future__ import annotations

from ....application.workflow._models import resolve_active_bucket_id
from ._errors import GoogleAuthProfileUnboundError


def resolve_active_profile(profile_override: str | None = None) -> str:
    """Return the AEAT profile name backing this Google OAuth call.

    Args:
        profile_override: Optional CLI `--profile` value. When non-empty
            this wins over the precedence chain, so a CLI invocation
            like `aeat config google login --profile business` reaches
            the right per-profile records even if a different profile
            is currently active.

    Returns:
        The resolved AEAT profile name. Always a non-empty string.

    Raises:
        GoogleAuthProfileUnboundError: When `profile_override` is empty
            or `None` and the operator-facing precedence chain resolves
            to `None`. The error carries a `suggestion` pointing to
            `aeat config init` and a `context` payload naming the
            resolution attempt for renderers.
    """

    override = (profile_override or "").strip()
    if override:
        return override

    resolved = resolve_active_bucket_id()
    if resolved is not None and resolved.strip():
        return resolved.strip()

    raise GoogleAuthProfileUnboundError(
        "no active AEAT profile bound and no --profile override given",
        context={"override": profile_override or "", "active_profile": resolved or ""},
        suggestion="aeat config init --tax-id <NIF>",
    )


__all__ = ["resolve_active_profile"]
