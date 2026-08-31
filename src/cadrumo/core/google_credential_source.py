"""Closed taxonomy for how :mod:`~adapters.outbound.google` obtains credentials.

:class:`~core.GoogleCredentialSourceKind` is the accepted-value set governing
which mechanism :mod:`~adapters.outbound.google` uses to produce a
``google.oauth2.credentials.Credentials``-shaped object for the Sheets/Drive
export mirror. Declared in ``core`` per ``aeat-architecture-boundaries``
(closed value sets are ``StrEnum`` in the innermost ring) and
``aeat-registry-authority-flow`` (a code-level, non-registry taxonomy still
belongs in the central authority, not scattered string literals).

See Also:
    :func:`~adapters.outbound.google.resolve_impersonated_credentials`
        Resolves
        :attr:`~core.GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION`
        into a real, short-lived-token ``Credentials`` object.
    :func:`~adapters.outbound.storage.build_google_credentials`
        Resolves :attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP`, the
        existing per-profile interactive-consent credential source.
"""

from __future__ import annotations

from enum import StrEnum


class GoogleCredentialSourceKind(StrEnum):
    """The closed set of mechanisms that can produce Google API credentials.

    Members:
        OAUTH_DESKTOP: The existing, default per-profile interactive OAuth
            Desktop consent flow (``aeat config google register`` /
            ``login``). Persists a long-lived refresh token per profile via
            :class:`~adapters.outbound.google.OAuthClient` and
            :class:`~adapters.outbound.google.OAuthToken`.
        SERVICE_ACCOUNT_IMPERSONATION: A shared Google service-account
            identity is impersonated via Application Default Credentials
            (ADC) plus IAM ``roles/iam.serviceAccountTokenCreator``. No
            long-lived credential is persisted by this application; a
            short-lived access token is re-derived from ADC and IAM on
            every use. See
            :class:`~adapters.outbound.google.GoogleImpersonationConfig`.
    """

    OAUTH_DESKTOP = "oauth_desktop"
    SERVICE_ACCOUNT_IMPERSONATION = "service_account_impersonation"


__all__ = ["GoogleCredentialSourceKind"]
