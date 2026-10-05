"""Whether a profile's stored Google sign-in can still be used.

A stored sign-in stops being usable in two ways this module recognises. It may
have been minted for a different client than the one this installation signs in
with, or stored before tokens recorded their client at all; such a token is
never presented to Google. Or Google may answer a token refresh with
``invalid_grant``, its one verdict for a grant the user revoked and for one
that expired. Both end the same way: the profile has to sign in again, which
is reported as a typed refusal rather than as a network failure.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .errors import (
    GoogleAuthPreconditionCondition,
    GoogleAuthSignInRequiredError,
    google_auth_no_action_verdict,
)
from .records import OAuthClient, OAuthToken

_ENDED_GRANT_ERROR = "invalid_grant"


def load_token_minted_for(profile: str, client: OAuthClient) -> OAuthToken | None:
    """Return the profile's stored token when ``client`` minted it.

    Args:
        profile: Profile whose stored sign-in is read.
        client: The client this installation signs in with.

    Returns:
        The stored token, or ``None`` when the profile has never signed in.

    Raises:
        :exc:`adapters.outbound.google.errors.GoogleAuthSignInRequiredError`:
            When a token is stored but names another client, or was stored in
            a shape that names none. No earlier shape is read.
    """
    # Imported here so the request executors that share this module do not
    # load the profile store to classify a transport failure.
    from .session_store import load_token

    try:
        token = load_token(profile)
    except ValidationError:
        raise GoogleAuthSignInRequiredError(
            "the stored Google sign-in does not name the client that minted it",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.SIGN_IN_CLIENT_BOUND,
                facts={"stored_token_readable": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        ) from None
    if token is None:
        return None
    if token.client_id != client.client_id:
        raise GoogleAuthSignInRequiredError(
            "the stored Google sign-in was minted for a different client",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.SIGN_IN_CLIENT_BOUND,
                facts={"stored_token_readable": True, "token_client_matches": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        )
    return token


def ended_grant_refusal(error: Exception, *, action: str) -> GoogleAuthSignInRequiredError | None:
    """Return the sign-in-required refusal when ``error`` is Google ending the grant.

    The credential refresh that reports this runs before a request is sent, or
    after Google has already rejected it as unauthorized, so the request the
    refresh was for has not taken effect.

    Args:
        error: Failure raised while executing a Google API request.
        action: Stable label of the request the refresh was for.

    Returns:
        The typed refusal, or ``None`` when ``error`` is any other failure.
    """
    try:
        from google.auth.exceptions import RefreshError
    except ImportError:
        return None
    if not isinstance(error, RefreshError):
        return None
    response = error.args[1] if len(error.args) > 1 else None
    if not isinstance(response, Mapping) or response.get("error") != _ENDED_GRANT_ERROR:
        return None
    return GoogleAuthSignInRequiredError(
        "Google no longer honours the stored sign-in",
        context={"action": action},
        precondition_verdict=google_auth_no_action_verdict(
            condition=GoogleAuthPreconditionCondition.GRANT_ACTIVE,
            facts={"grant_active": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


__all__ = ["ended_grant_refusal", "load_token_minted_for"]
