"""Google OAuth credential refresh lifecycle.

Refreshes an `OAuthToken` against Google's token endpoint when the
in-memory access token is missing, expired, or about to expire (5-minute
clock-skew buffer). Re-persists the refresh token after every
successful refresh because Google rotates it. Detects three special
cases at refresh time:

1. `invalid_grant` from Google → flips `OAuthMetadata.reauth_required=True`
   so the next CLI invocation surfaces the re-consent path. Never auto-
   retries; the operator must re-run `aeat config google login`.
2. Testing-project refresh tokens that have aged past Google's 7-day
   cap on the consent screen → emits a one-time warning the first time
   the elapsed window crosses six days, so the operator can re-consent
   before the credential expires.
3. Network failures → typed `GoogleAuthNetworkError` with retry hint.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ....core.config import Settings as _Settings
from ....core.i18n import tr
from ._errors import (
    GoogleAuthError,
    GoogleAuthExpiredError,
    GoogleAuthNetworkError,
    GoogleAuthRevokedError,
)
from ._records import REQUIRED_SCOPES, OAuthClient, OAuthMetadata, OAuthToken

# Window before nominal expiry inside which we treat the access token
# as already expired. Mirrors `google.auth.credentials._helpers`'s
# default. Picking the same buffer keeps our retry semantics aligned
# with the upstream library's own internal refresh trigger.
ACCESS_TOKEN_REFRESH_BUFFER: timedelta = timedelta(seconds=_Settings().aeat_google_oauth_access_refresh_buffer_s)

# Google's Testing-project consent screens cap refresh tokens at 7 days.
# We surface a one-time warning when the elapsed window crosses 6 days
# so the operator has 24h of lead-time to re-consent.
TESTING_PROJECT_TOKEN_LIFETIME: timedelta = timedelta(days=7)
TESTING_PROJECT_WARN_AFTER: timedelta = timedelta(days=6)


def is_token_expired(
    *,
    access_token_expiry: datetime | None,
    now: datetime,
    buffer: timedelta = ACCESS_TOKEN_REFRESH_BUFFER,
) -> bool:
    """Return ``True`` when the access token must be refreshed before use.

    A `None` expiry is treated as "no valid token in memory" (cold
    start), which always returns True so the caller acquires a fresh
    access token from the refresh-token grant.
    """

    if access_token_expiry is None:
        return True
    return now + buffer >= access_token_expiry


def detect_testing_project_warning(
    *,
    issued_at: datetime,
    now: datetime,
    last_refresh_at: datetime,
) -> str | None:
    """Surface the 7-day Testing-project warning at the right moment.

    Returns a warning string when the issued credential has aged past
    `TESTING_PROJECT_WARN_AFTER` (6 days) but the previous successful
    refresh predated that crossing. Returns `None` when:

    - The issued credential is still inside the warning window, OR
    - A previous refresh already crossed the warning threshold (so we
      don't spam the operator on every refresh once the window opens).
    """

    elapsed = now - issued_at
    if elapsed < TESTING_PROJECT_WARN_AFTER:
        return None
    if last_refresh_at - issued_at >= TESTING_PROJECT_WARN_AFTER:
        return None
    remaining = TESTING_PROJECT_TOKEN_LIFETIME - elapsed
    if remaining <= timedelta(0):
        return None
    return tr(
        "adapters.google.refresh.testing_project_cap_warning",
        hours_remaining=int(remaining.total_seconds() // 3600),
    )


def mark_reauth_required(metadata: OAuthMetadata) -> OAuthMetadata:
    """Return a copy of ``metadata`` with `reauth_required=True`.

    Used after `invalid_grant` so subsequent commands can surface the
    re-consent advisory without re-running the failed refresh.
    """

    return metadata.model_copy(update={"reauth_required": True})


def refresh_credentials(
    *,
    client: OAuthClient,
    token: OAuthToken,
    metadata: OAuthMetadata,
    now: datetime,
) -> tuple[OAuthToken, OAuthMetadata, str, str | None]:
    """Run one refresh cycle and return rotated artefacts plus advisories.

    Always executes the real
    `google.oauth2.credentials.Credentials.refresh(...)` against
    Google's token endpoint. No test seams. Failure modes surface as
    typed `GoogleAuthError` subclasses with concrete remediation context.

    Args:
        client: The operator's OAuth client metadata.
        token: The current refresh credential (may rotate after this call).
        metadata: The current audit metadata. The output metadata
            updates `last_refresh_at` and may flip `reauth_required`.
        now: The current UTC timestamp.

    Returns:
        `(new_token, new_metadata, new_access_token, warning)`. The
        `warning` field is non-None when the operator should be nudged
        toward re-consent before the Testing-project cap fires.

    Raises:
        GoogleAuthRevokedError: When the refresh endpoint returns
            `invalid_grant`. The metadata returned via `mark_reauth_required`
            on the exception's `context["metadata"]` field captures the
            state callers must persist before raising onward.
        GoogleAuthExpiredError: When `metadata.reauth_required` was
            already True at call entry — the refresh path is closed
            and only `aeat config google login` can recover.
        GoogleAuthNetworkError: When the token endpoint is unreachable.
    """

    if metadata.reauth_required:
        raise GoogleAuthExpiredError(
            "google OAuth credential is marked reauth_required; refresh path is closed",
            context={"account_email": metadata.account_email},
            suggestion="aeat config google login",
            translated_message="adapters.google.refresh.errors.reauth_required",
        )

    try:
        new_refresh_token, new_access_token, _ = _refresh_against_google(client, token)
    except GoogleAuthRevokedError as exc:
        # Capture the marked-for-reauth metadata on the exception so the
        # caller can persist it before re-raising onward.
        flipped = mark_reauth_required(metadata)
        exc.context = {**(exc.context or {}), "metadata": flipped.model_dump(mode="json")}
        raise
    except GoogleAuthError:
        raise
    except OSError as exc:
        raise GoogleAuthNetworkError(
            f"google OAuth token endpoint unreachable: {exc}",
            suggestion=tr("adapters.google.refresh.suggestions.check_network"),
            translated_message="adapters.google.refresh.errors.token_endpoint_unreachable",
        ) from exc

    rotated_token = OAuthToken(refresh_token=new_refresh_token, token_uri=token.token_uri)
    updated_metadata = metadata.model_copy(update={"last_refresh_at": now})
    warning = detect_testing_project_warning(
        issued_at=metadata.issued_at,
        now=now,
        last_refresh_at=metadata.last_refresh_at,
    )
    return rotated_token, updated_metadata, new_access_token, warning


def _refresh_against_google(client: OAuthClient, token: OAuthToken) -> tuple[str, str, datetime]:
    """Run the real `Credentials.refresh(...)` cycle against `oauth2.googleapis.com`.

    Imports `google-auth` lazily so a missing transitive dependency
    surfaces as a typed `GoogleAuthNetworkError` rather than an opaque
    ImportError.

    Returns:
        `(new_refresh_token, new_access_token, new_expiry_utc)`.

    Raises:
        GoogleAuthRevokedError: Maps Google's `invalid_grant` response.
        GoogleAuthNetworkError: Maps transport failures.
    """

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise GoogleAuthNetworkError(
            f"google-auth not importable: {exc}",
            suggestion="uv sync",
            translated_message="adapters.google.refresh.errors.google_auth_not_importable",
        ) from exc

    creds = Credentials(
        token=None,
        refresh_token=token.refresh_token,
        token_uri=token.token_uri,
        client_id=client.client_id,
        client_secret=client.client_secret,
        scopes=list(REQUIRED_SCOPES),
    )
    try:
        creds.refresh(Request())
    except Exception as exc:
        message = str(exc).lower()
        if "invalid_grant" in message or "revoked" in message:
            raise GoogleAuthRevokedError(
                f"google OAuth refresh refused: {exc}",
                suggestion="aeat config google login",
                translated_message="adapters.google.refresh.errors.refresh_refused",
            ) from exc
        raise GoogleAuthNetworkError(
            f"google OAuth refresh failed: {exc}",
            suggestion=tr("adapters.google.refresh.suggestions.check_network"),
            translated_message="adapters.google.refresh.errors.refresh_failed",
        ) from exc

    return (
        str(creds.refresh_token or token.refresh_token),
        str(creds.token or ""),
        creds.expiry if creds.expiry is not None else datetime.now(UTC),
    )


__all__ = [
    "ACCESS_TOKEN_REFRESH_BUFFER",
    "TESTING_PROJECT_TOKEN_LIFETIME",
    "TESTING_PROJECT_WARN_AFTER",
    "detect_testing_project_warning",
    "is_token_expired",
    "mark_reauth_required",
    "refresh_credentials",
]
