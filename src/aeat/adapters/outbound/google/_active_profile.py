"""Active-profile resolver for the Google OAuth Desktop integration.

Every `aeat config google ...` command and every secure-store read or
write the OAuth flow performs is scoped to a single AEAT profile.
This module exposes one entry point — `resolve_active_profile` —
that the CLI surface and the secure-store accessors call to obtain
that profile's immutable UUID identity. Resolution flows through the
operator-facing precedence chain in
`application/workflow/_models.resolve_active_bucket_id`
(Settings override > plaintext pointer file); per-invocation
`--profile` overrides on `aeat config google` verbs are removed
so profile selection is one chain, one source of truth.

There is no global Google session, no shared cross-profile token, and
no multi-account binding within a single profile. The whole-package
contract is enforced at this single chokepoint.
"""

from __future__ import annotations

from ....core import resolve_active_bucket_id
from ....core.i18n import tr
from ._errors import GoogleAuthProfileUnboundError


def resolve_active_profile() -> str:
    """Return the AEAT profile UUID backing this Google OAuth call.

    Returns:
        The resolved profile's immutable UUID identity. Always a
        non-empty string.

    Raises:
        GoogleAuthProfileUnboundError: When the operator-facing
            precedence chain resolves to ``None``. The error carries
            a `suggestion` pointing to `aeat config profile create NAME` and a
            `context` payload naming the resolution attempt for
            renderers.
    """
    resolved = resolve_active_bucket_id()
    if resolved is not None and resolved.strip():
        return resolved.strip()

    raise GoogleAuthProfileUnboundError(
        "no active AEAT profile bound for Google OAuth",
        context={"active_profile": resolved or ""},
        suggestion=tr("adapters.google.profile_binding.suggestions.create_profile"),
        translated_message="adapters.google.profile_binding.errors.no_active_profile",
    )


__all__ = ["resolve_active_profile"]
