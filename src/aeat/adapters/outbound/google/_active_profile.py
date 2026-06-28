"""Active-profile resolver for the Google OAuth Desktop integration.

Every ``aeat config google ...`` command and every secure-store read or write
performed by :mod:`aeat.adapters.outbound.google._oauth_flow` and
:mod:`aeat.adapters.outbound.google._session_store` is scoped to one AEAT
profile. :func:`resolve_active_profile` obtains that profile's immutable bucket
UUID through :func:`aeat.core.resolve_active_bucket_id`, the operator-facing
precedence chain driven by :class:`aeat.core.config.Settings` and the plaintext
active-profile pointer file.

There is no global Google session, no shared cross-profile token, and no
multi-account binding within a single profile. A missing profile is raised as
:class:`GoogleAuthProfileUnboundError` so the CLI and storage factory render
the same localised repair guidance.
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
        :class:`GoogleAuthProfileUnboundError`: When the
            :func:`aeat.core.resolve_active_bucket_id` precedence chain resolves
            to no profile. The error carries a ``suggestion`` pointing to
            ``aeat config profile create NAME`` and a ``context`` payload naming
            the failed resolution attempt for renderers.
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
