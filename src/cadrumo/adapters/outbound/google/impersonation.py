"""Service-account impersonation credential source for Google API access.

A gestor operating for several represented entities may want one shared
Google identity backing the Sheets/Drive export mirror instead of every team
member running the interactive per-profile OAuth Desktop consent flow
(:func:`~adapters.outbound.google.run_login_flow`). Google's supported mechanism for
this is service-account (SA) impersonation: a locally-discoverable identity —
Application Default Credentials (ADC) — is granted IAM
``roles/iam.serviceAccountTokenCreator`` on a target SA, and every API call mints
a short-lived, scoped access token for that SA rather than presenting the ADC
identity's own token directly.

:class:`~adapters.outbound.google.GoogleImpersonationConfig` is the typed,
frozen configuration record; :func:`~adapters.outbound.google.resolve_impersonated_credentials`
performs the two-step resolution (ADC discovery, then impersonation wrapping)
and eagerly validates the grant with one real token refresh so a misconfigured
SA fails loudly at resolution time rather than deep inside a later Sheets write.

That eager refresh also covers ADC freshness: Google's own impersonated-
credentials refresh implementation refreshes a stale or invalid SOURCE
credential internally before minting the impersonated token
(``google.auth.impersonated_credentials.Credentials._perform_refresh_token``
calls ``source_credentials.refresh(request)`` whenever
``source_credentials.token_state`` is ``STALE`` or ``INVALID``), so a
merely-stale (but still refreshable) ADC user credential is transparently
renewed with no operator action.
:func:`~adapters.outbound.google.resolve_impersonated_credentials` additionally
distinguishes the two ways that refresh can still fail: a
genuinely revoked/expired ADC SOURCE credential (the operator's local
``gcloud auth application-default login`` grant itself is dead) raises
:class:`~adapters.outbound.google.GoogleAuthAdcStaleError` naming the
``gcloud`` re-login remediation, while every other refresh failure (a real IAM
Token Creator grant problem on ``target_principal``) raises
:class:`~adapters.outbound.google.GoogleAuthImpersonationRefusedError` naming
the IAM role-grant remediation instead. Per
``no-silent-under-declaration``, a stale token is never silently reused or
misreported as an unrelated IAM refusal.

Unlike :func:`~adapters.outbound.storage.build_google_credentials` (the
existing OAuth-Desktop path), the resolved credential itself persists
NOTHING: ADC is discovered fresh from the host environment on every call
(``GOOGLE_APPLICATION_CREDENTIALS``, ``gcloud`` user credentials, or an
attached workload identity), and the impersonated access token is held only
in memory for the process lifetime, never written to secure storage or
workflow state (``sensitive-financial-data-secure-storage-only``: there is
no long-lived secret here to protect because none is stored).
:class:`~adapters.outbound.google.GoogleCredentialSourceSelection` persists only
the non-secret CONFIGURATION (which kind a profile has chosen, and the target SA
email / scopes) — never a credential.

The CLI verb and locale strings for configuring this source are still
deferred; the
per-profile persistence and
:func:`~adapters.outbound.storage.build_google_credentials` dispatch wiring
described there are implemented by
:class:`~adapters.outbound.google.GoogleCredentialSourceSelection` and its
session-store persistence functions, consumed by the factory.

See Also:
    :class:`~core.GoogleCredentialSourceKind`
        The closed taxonomy this module implements one member of.
    :func:`~adapters.outbound.storage.build_google_credentials`
        The existing default (interactive OAuth Desktop) credential source
        this module is an alternative to, never a replacement for; also the
        dispatch point that reads
        :class:`~adapters.outbound.google.GoogleCredentialSourceSelection`.
    :data:`~adapters.outbound.google.REQUIRED_SCOPES`
        The OAuth-Desktop scope bundle; this module's default
        ``target_scopes`` excludes the identity scopes (``openid``,
        ``email``) that only apply to a human OAuth consent grant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG, ActionEvidenceProvenance, GoogleCredentialSourceKind, NoRecoveryOutcome
from .errors import GoogleAuthError, GoogleAuthPreconditionCondition, google_auth_no_action_verdict
from .records import DRIVE_FILE_SCOPE, SHEETS_SCOPE

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


class GoogleAuthAdcStaleError(GoogleAuthError):
    """Raised when a discovered ADC source credential can no longer be refreshed.

    ADC was discovered (unlike
    :class:`~adapters.outbound.google.GoogleAuthAdcUnavailableError`, where
    discovery itself fails), but the source credential's own refresh failed —
    the common case is a ``gcloud auth application-default login`` grant that was
    revoked or expired since it was issued. This is distinct from
    :class:`~adapters.outbound.google.GoogleAuthImpersonationRefusedError`: here
    the ADC identity itself is the problem (re-authenticate it), not the IAM
    grant on ``target_principal`` (grant Token Creator).
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
            (:data:`~adapters.outbound.google.DRIVE_FILE_SCOPE`,
            :data:`~adapters.outbound.google.SHEETS_SCOPE`); the identity
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


class GoogleCredentialSourceSelection(BaseModel):
    """Per-profile persisted choice of :class:`~core.GoogleCredentialSourceKind`.

    Persisted via
    :func:`~adapters.outbound.google.save_credential_source_selection` /
    :func:`~adapters.outbound.google.load_credential_source_selection` and read
    by :func:`~adapters.outbound.storage.build_google_credentials` to decide
    whether to hydrate the default per-profile OAuth-Desktop credential or
    dispatch to
    :func:`~adapters.outbound.google.resolve_impersonated_credentials`.

    Carries no long-lived secret: ``kind = OAUTH_DESKTOP`` needs no
    additional field (the existing
    :class:`~adapters.outbound.google.OAuthClient` /
    :class:`~adapters.outbound.google.OAuthToken` records already hold that
    path's credential); ``kind = SERVICE_ACCOUNT_IMPERSONATION`` requires
    ``impersonation`` to be populated with the target SA email and scopes, which
    are configuration, not a secret — the actual access token is re-derived from
    Application Default Credentials on every use and is never written to secure
    storage.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: GoogleCredentialSourceKind = GoogleCredentialSourceKind.OAUTH_DESKTOP
    impersonation: GoogleImpersonationConfig | None = None

    @model_validator(mode="after")
    def _impersonation_config_required_for_impersonation_kind(self) -> GoogleCredentialSourceSelection:
        if self.kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION and self.impersonation is None:
            raise ValueError(
                "impersonation must be set when kind is service_account_impersonation",
            )
        if self.kind is GoogleCredentialSourceKind.OAUTH_DESKTOP and self.impersonation is not None:
            raise ValueError("impersonation must be unset when kind is oauth_desktop")
        return self


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

    Three-step resolution:

    1. Discover Application Default Credentials via ``google.auth.default()``,
       scoped to ``config.target_scopes``.
    2. Eagerly refresh the discovered SOURCE credential when it is stale or
       invalid
       (:func:`~adapters.outbound.google.impersonation._ensure_source_credential_is_fresh`).
       A merely-stale
       ADC user credential (past its access-token lifetime but still holding
       a live refresh token) is silently renewed here — the normal case for
       a long-running process reusing a ``gcloud auth application-default
       login`` grant. A genuinely dead grant (revoked, expired refresh
       token) raises
       :class:`~adapters.outbound.google.GoogleAuthAdcStaleError` naming the
       exact ``gcloud`` re-authentication remediation, distinct from an IAM
       grant problem on the impersonation target.
    3. Wrap the (now-fresh) source credentials in
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
        GoogleAuthAdcStaleError: When ADC was discovered but its own
            refresh (renewing an expired access token, or exchanging a
            long-lived refresh token) fails — the ADC identity itself must
            be re-authenticated.
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
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.ADC_CLIENT_AVAILABLE,
                facts={"adc_client_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc

    try:
        source_credentials, _project_id = google.auth.default(scopes=list(config.target_scopes))
    except google.auth.exceptions.DefaultCredentialsError as exc:
        raise GoogleAuthAdcUnavailableError(
            f"Application Default Credentials not found: {exc}",
            context={"target_principal": config.target_principal},
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.ADC_AVAILABLE,
                facts={"adc_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc

    _ensure_source_credential_is_fresh(
        source_credentials,
        target_principal=config.target_principal,
    )

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
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.IAM_CREDENTIAL_MINTED,
                facts={"iam_token_minted": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc

    return impersonated


def _ensure_source_credential_is_fresh(
    source_credentials: Credentials,
    *,
    target_principal: str,
) -> None:
    """Eagerly refresh ``source_credentials`` when stale or invalid.

    ``google.auth.impersonated_credentials.Credentials._perform_refresh_token``
    already refreshes a stale/invalid source credential internally on every
    impersonated-token mint, so this call is not required for correctness —
    it exists to fail with an ADC-specific, actionable remediation
    (``GoogleAuthAdcStaleError``: "re-run ``gcloud auth application-default
    login``") the moment the SOURCE credential itself cannot be renewed,
    rather than letting that failure surface, unattributed, as an
    :class:`~adapters.outbound.google.GoogleAuthImpersonationRefusedError`
    naming an unrelated IAM role-grant remedy once it is wrapped for
    impersonation.

    A credential with no expiry (``token_state`` never ``STALE``/``INVALID``
    for a non-expiring source, e.g. some workload-identity credentials) is
    left untouched — there is nothing to refresh.
    """
    import google.auth.credentials
    import google.auth.exceptions
    import google.auth.transport.requests

    if source_credentials.token_state not in (
        google.auth.credentials.TokenState.STALE,
        google.auth.credentials.TokenState.INVALID,
    ):
        return

    try:
        source_credentials.refresh(google.auth.transport.requests.Request())
    except google.auth.exceptions.RefreshError as exc:
        raise GoogleAuthAdcStaleError(
            f"Application Default Credentials could not be refreshed: {exc}",
            context={"target_principal": target_principal},
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.ADC_SOURCE_FRESH,
                facts={"adc_source_fresh": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc


__all__ = [
    "GoogleAuthAdcStaleError",
    "GoogleAuthAdcUnavailableError",
    "GoogleAuthImpersonationRefusedError",
    "GoogleCredentialSourceSelection",
    "GoogleImpersonationConfig",
    "describe_impersonation_target",
    "resolve_impersonated_credentials",
]
