"""Active-profile resolver for the Google OAuth Desktop integration.

Every ``aeat config google ...`` command and every secure-store read or write
performed by :mod:`adapters.outbound.google._oauth_flow` and
:mod:`adapters.outbound.google._session_store` is scoped to one AEAT
profile. :func:`adapters.outbound.google.resolve_active_profile` obtains
that profile's immutable bucket UUID through
:func:`core.resolve_active_bucket_id`, the operator-facing precedence
chain driven by :class:`core.config.Settings` and the plaintext
active-profile pointer file.

There is no global Google session, no shared cross-profile token, and no
multi-account binding within a single profile. A missing profile is raised as
:exc:`adapters.outbound.google.GoogleAuthProfileUnboundError` so the CLI
and storage factory render the same localised repair guidance.
"""

from __future__ import annotations

from ....core import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.bucket_pointer import resolve_active_bucket_id
from ._errors import GoogleAuthPreconditionCondition, GoogleAuthProfileUnboundError, google_auth_no_action_verdict


def resolve_active_profile() -> str:
    """Return the AEAT profile UUID backing this Google OAuth call.

    Returns:
        The resolved profile's immutable UUID identity. Always a
        non-empty string.

    Raises:
        :exc:`adapters.outbound.google.GoogleAuthProfileUnboundError`:
            When the :func:`core.resolve_active_bucket_id` precedence
            chain resolves to no profile. The error carries factual context
            naming the failed resolution attempt for renderers.
    """
    resolved = resolve_active_bucket_id()
    if resolved is not None and resolved.strip():
        return resolved.strip()

    raise GoogleAuthProfileUnboundError(
        "no active AEAT profile bound for Google OAuth",
        context={"active_profile": resolved or ""},
        translated_message="adapters.google.profile_binding.errors.no_active_profile",
        precondition_verdict=google_auth_no_action_verdict(
            condition=GoogleAuthPreconditionCondition.ACTIVE_PROFILE_RESOLVED,
            facts={"active_profile_resolved": False},
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


__all__ = ["resolve_active_profile"]
