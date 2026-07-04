"""Service-account impersonation credential source for Google API access.

A gestor operating for several represented entities may want one shared
Google identity backing the Sheets/Drive export mirror instead of every team
member running the interactive per-profile OAuth Desktop consent flow
(:mod:`adapters.outbound.google._oauth_flow`). Google's supported mechanism
for this is service-account (SA) impersonation: a locally-discoverable
identity — Application Default Credentials (ADC) — is granted IAM
``roles/iam.serviceAccountTokenCreator`` on a target SA, and every API call
mints a short-lived, scoped access token for that SA rather than presenting
the ADC identity's own token directly.

:class:`GoogleImpersonationConfig` is the typed, frozen configuration record;
:func:`resolve_impersonated_credentials` performs the two-step resolution
(ADC discovery, then impersonation wrapping) and eagerly validates the grant
with one real token refresh so a misconfigured SA fails loudly at resolution
time rather than deep inside a later Sheets write.

Unlike :func:`adapters.outbound.storage.build_google_credentials` (the
existing OAuth-Desktop path), this module persists NOTHING: ADC is
discovered fresh from the host environment on every call
(``GOOGLE_APPLICATION_CREDENTIALS``, ``gcloud`` user credentials, or an
attached workload identity), and the impersonated access token is held only
in memory for the process lifetime, never written to secure storage or
workflow state
(``sensitive-financial-data-secure-storage-only``: there is no
long-lived secret here to protect because none is stored).

This module is a core-only slice: no CLI verb, no persisted per-profile
selection, and no wiring into :func:`adapters.outbound.storage.get_storage_provider`
exist yet. See ``.vault/adr/2026-07-04-google-sa-impersonation-adr.md``
(``google-sa-impersonation`` ADR) for the accepted design and the explicitly
deferred follow-up (GitHub issue #591 remainder).

See Also:
    :class:`core.GoogleCredentialSourceKind`
        The closed taxonomy this module implements one member of.
    :func:`adapters.outbound.storage.build_google_credentials`
        The existing default (interactive OAuth Desktop) credential source
        this module is an alternative to, never a replacement for.
    :data:`adapters.outbound.google.REQUIRED_SCOPES`
        The OAuth-Desktop scope bundle; this module's default
        ``target_scopes`` excludes the identity scopes (``openid``,
        ``email``) that only apply to a human OAuth consent grant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG
from ._errors import GoogleAuthError
from ._records import DRIVE_FILE_SCOPE, SHEETS_SCOPE

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

# The data-access scope subset of REQUIRED_SCOPES. A service account has no
# "signed-in user" identity to surface via openid/userinfo.email, so those two
# identity scopes (meaningful only for a human OAuth consent screen) are
# excluded from the SA-impersonation default.
_DEFAULT_IMPERSONATION_SCOPES: tuple[str, ...] = (DRIVE_FILE_SCOPE, SHEETS_SCOPE)

# Google's impersonation credentials API caps the minted token lifetime at
# one hour; a caller requesting more receives a clear upstream rejection
# rather than a silently-clamped value.
_MAX_LIFETIME_S = 3600


class GoogleAuthAdcUnavailableError(GoogleAuthError):
    """Raised when Application Default Credentials cannot be discovered on this host.

    Emitted when ``google.auth.default()`` fails to locate any of the ADC
    discovery sources (``GOOGLE_APPLICATION_CREDENTIALS`` env var, the
    ``gcloud auth application-default login`` user credential file, or an
    attached GCE/GKE/Cloud Run workload identity).
    """


class GoogleAuthImpersonationRefusedError(GoogleAuthError):
    """Raised when IAM refuses to mint an impersonated token for the target principal.

    The most common cause is that the ADC identity lacks
    ``roles/iam.serviceAccountTokenCreator`` on ``target_principal`` (or, for
    a chained ``delegates`` sequence, on the first delegate). The exception
    context carries ``target_principal`` so a caller can render the exact
    IAM grant the operator needs to add.
    """


class GoogleImpersonationConfig(BaseModel):
    """Typed, frozen configuration for one service-account impersonation grant.

    Attributes:
        target_principal: The service-account email being impersonated
            (e.g. ``"aeat-export@my-project.iam.gserviceaccount.com"``).
        target_scopes: OAuth scopes requested for the minted token. Defaults
            to the Sheets/Drive data-access scopes
            (:data:`adapters.outbound.google.DRIVE_FILE_SCOPE`,
            :data:`adapters.outbound.google.SHEETS_SCOPE`); the identity
            scopes (``openid``, ``email``) do not apply to a service account
            and are intentionally excluded from the default.
        delegates: Optional chained impersonation sequence. When set, each
            entry must hold Token Creator on the next, and the ADC identity
            must hold Token Creator on ``delegates[0]``.
        subject: Optional user email to impersonate via Workspace
            domain-wide delegation. Only meaningful when the target SA has
            been granted domain-wide delegation by a Workspace
            administrator; this module cannot verify that grant and
            surfaces whatever refusal Google's token endpoint returns.
        lifetime_s: Requested token lifetime in seconds, bounded to
            Google's 3600s ceiling.
    """

    model_config = STRICT_FROZEN_CONFIG

    target_principal: str = Field(min_length=1)
    target_scopes: tuple[str, ...] = Field(default=_DEFAULT_IMPERSONATION_SCOPES, min_length=1)
    delegates: tuple[str, ...] = Field(default=())
    subject: str | None = Field(default=None, min_length=1)
    lifetime_s: int = Field(default=_MAX_LIFETIME_S, gt=0, le=_MAX_LIFETIME_S)

    @field_validator("target_principal")
    @classmethod
    def _target_principal_looks_like_an_email(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or "@" not in stripped:
            raise ValueError(f"target_principal must be a service-account email; got {value!r}")
        return stripped

    @field_validator("delegates")
    @classmethod
    def _delegates_look_like_emails(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for delegate in value:
            if not delegate.strip() or "@" not in delegate:
                raise ValueError(f"each delegate must be a service-account email; got {delegate!r}")
        return value


def describe_impersonation_target(config: GoogleImpersonationConfig) -> str:
    """Return the exact service-account email ``config`` would impersonate.

    Returns ``config.target_principal`` verbatim. Exists as a named accessor
    (rather than reading the field directly at every call site) so a future
    CLI ``show``/``status`` verb can surface "you are about to grant IAM
    roles to exactly this identity" without requiring a live token exchange
    first — satisfying the operator's need to confirm the SA identity before
    approving an IAM role grant.
    """
    return config.target_principal


def resolve_impersonated_credentials(config: GoogleImpersonationConfig) -> Credentials:
    """Resolve ``config`` into a validated, impersonated ``Credentials`` object.

    Two-step resolution:

    1. Discover Application Default Credentials via ``google.auth.default()``,
       scoped to ``config.target_scopes``.
    2. Wrap the discovered source credentials in
       ``google.auth.impersonated_credentials.Credentials`` targeting
       ``config.target_principal``, then eagerly call ``.refresh()`` once so
       a misconfigured grant (missing Token Creator role, wrong scopes,
       revoked domain-wide delegation) is caught here rather than silently
       later inside a Sheets/Drive call.

    Args:
        config: The impersonation target and scope configuration.

    Returns:
        A ``google.auth.impersonated_credentials.Credentials`` instance
        carrying a valid, short-lived access token for ``target_principal``.
        Nothing from this resolution is persisted by this application.

    Raises:
        GoogleAuthAdcUnavailableError: When ADC discovery finds no usable
            credential source on this host.
        GoogleAuthImpersonationRefusedError: When IAM refuses to mint a
            token for ``target_principal`` (commonly a missing Token
            Creator grant, or a ``subject`` requiring domain-wide
            delegation the target SA was never granted).
    """
    try:
        import google.auth
        import google.auth.exceptions
        import google.auth.impersonated_credentials
        import google.auth.transport.requests
    except ImportError as exc:
        raise GoogleAuthAdcUnavailableError(
            f"google-auth is not importable: {exc}",
            context={"target_principal": config.target_principal},
            suggestion="pip install aeat[google]",
        ) from exc

    try:
        source_credentials, _project_id = google.auth.default(scopes=list(config.target_scopes))
    except google.auth.exceptions.DefaultCredentialsError as exc:
        raise GoogleAuthAdcUnavailableError(
            f"Application Default Credentials not found: {exc}",
            context={"target_principal": config.target_principal},
            suggestion="gcloud auth application-default login",
        ) from exc

    impersonated = google.auth.impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=config.target_principal,
        target_scopes=list(config.target_scopes),
        delegates=list(config.delegates) or None,
        subject=config.subject,
        lifetime=config.lifetime_s,
    )

    try:
        impersonated.refresh(google.auth.transport.requests.Request())
    except google.auth.exceptions.RefreshError as exc:
        raise GoogleAuthImpersonationRefusedError(
            f"IAM refused to mint an impersonated token for {config.target_principal!r}: {exc}",
            context={"target_principal": config.target_principal},
            suggestion=(f"grant roles/iam.serviceAccountTokenCreator to the ADC identity on {config.target_principal}"),
        ) from exc

    return impersonated


__all__ = [
    "GoogleAuthAdcUnavailableError",
    "GoogleAuthImpersonationRefusedError",
    "GoogleImpersonationConfig",
    "describe_impersonation_target",
    "resolve_impersonated_credentials",
]
