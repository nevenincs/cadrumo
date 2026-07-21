"""Operator-facing auth result contracts.

These records project provider catalogue entries, readiness checks, live-login
results, and preflight state through :class:`AuthProvidersReport`,
:class:`AuthStatusResult`, :class:`AuthTestResult`, and
:class:`LiveAuthPreflightReport`.

See Also:
    :mod:`application.auth._operator`
        Application services that construct these result contracts for CLI
        commands.
    :mod:`application.state_projection`
        Canonical readiness projection consumed by status and test results.
    :class:`application.workflow.WorkflowState`
        Encrypted state envelope carrying the persisted
        :class:`application.workflow.AuthState`.
    :class:`core.AuthProviderDescription`
        Provider-readiness description that feeds provider catalogue output.
    :class:`application.auth.AuthenticatedAeatSessionResult`
        Live-session result consumed by :class:`AuthLoginResult`.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import CadrumoError
from ._catalogue import AuthProviderListing


class AuthProviderReservedError(CadrumoError, ValueError):
    """Raised when a known provider slot is reserved but not implemented."""


class AuthConfigureNoActiveBucketError(CadrumoError):
    """Raised when auth configuration runs before an active profile bucket exists."""


class AuthConfigureDanglingActiveProfileError(CadrumoError, ValueError):
    """Raised when the active-profile pointer does not resolve to a registered bucket."""


class AuthLoginNotEnabledError(CadrumoError):
    """Raised when pytest invokes ``auth login`` without the live-test opt-in enabled."""


class AuthLoginPreconditionError(CadrumoError):
    """Raised when ``auth login`` cannot proceed because the configured provider is unusable."""


class AuthProvidersReport(BaseModel):
    """Auth provider catalogue projected for operator output."""

    model_config = _STRICT_FROZEN

    providers: tuple[AuthProviderListing, ...]


class AuthConfigureResult(BaseModel):
    """Result of configuring an auth provider in workflow state.

    The provider selection has already been written to
    :class:`application.workflow.AuthState` inside
    :class:`application.workflow.WorkflowState` when this result is
    returned.

    ``complete`` reports whether the provider is now operationally
    usable. The certificate provider configured without a resolvable
    ``--file`` records the provider selection but is NOT operationally
    ready: ``complete`` is ``False`` and ``incomplete_reason`` states a
    certificate path is still required. The operator must never be told
    "configured" when the provider cannot yet be used.
    """

    model_config = _STRICT_FROZEN

    provider: str
    file: str = ""
    complete: bool = True
    incomplete_reason: str = ""
    active_profile: str = ""
    profile_tax_id_present: bool = False
    provider_identity_present: bool = False
    identity_alignment: str = ""
    identity_alignment_detail: str = ""
    next_action: str = ""


class AuthStatusResult(BaseModel):
    """Current local auth readiness state.

    Built from
    :class:`application.state_projection.OperatorStateProjection`.
    Provider readiness mirrors
    :class:`application.state_projection.ProjectionAuthReadiness`;
    active-profile fields mirror
    :class:`application.state_projection.ProjectionActiveProfile`.
    """

    model_config = _STRICT_FROZEN

    provider: str = ""
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    active_profile: str = ""
    active_profile_status: str = ""
    active_profile_registered: bool = False
    active_profile_record_present: bool = False
    active_profile_next_action: str = ""
    backend_configured: bool = False
    backend_available: bool = False
    certificate_path: str = ""
    health_severity: str = ""
    health_summary: str = ""


class AuthTestResult(AuthStatusResult):
    """Auth readiness plus a deeper local readiness probe.

    ``auth status`` is a pure read of the canonical state projection.
    ``auth test`` carries every field ``auth status`` does - so the two
    can never disagree on ``configured`` - and runs a real per-provider
    local probe. For the certificate provider the probe opens the
    ``.p12`` file, parses the PKCS#12 envelope, classifies the bundle
    health (``ok`` / ``expired`` / ``expiring`` / ``corrupt`` /
    ``unreadable``), and surfaces the verdict as ``probe_result``. For
    Cl@ve Movil the probe classifies the configured DNI/NIE through the
    real identity classifier and reports ``ok`` / ``invalid_identity`` /
    ``identity_unset``. The persisted-session inspection ``auth status``
    cannot perform - does an encrypted AEAT session token exist on disk
    and is it still within its idle deadline - is also reported here
    (round-3 G5 + round-5 M4).

    Attributes:
        persisted_session_present: Whether an encrypted AEAT session
            token is on disk for the probed provider.
        persisted_session_expired: Whether that token has passed its
            idle deadline; ``None`` when no token is present.
        probe_summary: A one-line operator-facing verdict of the local
            probe.
        probe_result: A typed verdict of the per-provider probe. Values
            include ``ok``, ``expired``, ``expiring``, ``corrupt``,
            ``unreadable``, ``invalid_identity``, ``identity_unset``,
            ``no_path_set``, ``file_missing``, ``no_provider``. Empty
            only when no provider could be resolved.
    """

    model_config = _STRICT_FROZEN

    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    persisted_session_state: str = ""
    probe_summary: str = ""
    probe_result: str = ""


class LiveAuthPreflightReport(BaseModel):
    """Redacted live-auth readiness report rendered before operator approval waits.

    Combines the :class:`AuthTestResult` readiness fields with live-auth
    identity-alignment settings before
    :class:`core.access_gate.AeatAccessGate` can allow an authenticated
    read.
    """

    model_config = _STRICT_FROZEN

    provider: str = ""
    configured: bool = False
    available: bool = False
    active_profile: str = ""
    active_profile_status: str = ""
    active_profile_registered: bool = False
    active_profile_record_present: bool = False
    profile_tax_id_present: bool = False
    provider_identity_present: bool = False
    identity_alignment: str = ""
    identity_kind: str = ""
    auth_mode: str = ""
    prefer_non_qr: bool | None = None
    timeout_ms: int | None = None
    dni_fecha_configured: bool | None = None
    nie_soporte_configured: bool | None = None
    certificate_path_configured: bool | None = None
    certificate_file_present: bool | None = None
    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    persisted_session_state: str = ""
    probe_result: str = ""


class AuthLoginResult(BaseModel):
    """Result of an operator-triggered live authentication attempt.

    Summarises the
    :class:`application.auth.AuthenticatedAeatSessionResult` produced by
    the provider-session lifecycle without exposing session material.
    """

    model_config = _STRICT_FROZEN

    provider: str
    authenticated: bool
    reused_persisted_session: bool
    fresh: bool
    removed_sessions: int
    acquired_lock: bool
    reset_lock_state: str = ""
    verification_status: str = ""


class AuthOperationScopeConflictError(CadrumoError, ValueError):
    """Raised when ``--provider`` and ``--all`` are requested together."""


class AuthCleanupInProgressError(CadrumoError):
    """Raised when a non-resume auth mutation meets durable cleanup intent."""


class CertificateSecretMutationInProgressError(CadrumoError):
    """Raised when another auth mutation meets durable certificate-secret intent."""


class AuthProviderNotConfiguredError(CadrumoError, ValueError):
    """Raised when an auth operation has neither an explicit nor configured provider."""


class AuthLogoutResult(BaseModel):
    """Secret-free result of terminating local auth sessions."""

    model_config = _STRICT_FROZEN

    bucket_id: str
    providers: tuple[str, ...]
    removed_sessions: int
    cleared_session_state: bool


class AuthResetResult(BaseModel):
    """Secret-free result of removing local provider auth configuration."""

    model_config = _STRICT_FROZEN

    bucket_id: str
    providers: tuple[str, ...]
    removed_sessions: int
    cleared_provider_configuration: bool
    cleared_locks: int
    removed_certificate_sources: int
    removed_certificate_secrets: int


class CertificateSourceNotFoundError(CadrumoError, KeyError):
    """Raised when an operator names a certificate source that is not registered."""


class CertificateSourcePayload(BaseModel):
    """One registered certificate source, operator-facing.

    Projects :class:`application.workflow.CertificateSourceRecord` for the
    ``certificate register`` / ``certificate list`` verbs. Never carries
    certificate passwords or key material — only the filesystem
    reference already stored in workflow state.
    """

    model_config = _STRICT_FROZEN

    name: str
    certificate_path: str
    friendly_name: str = ""
    active: bool = False
    registered_at: str = ""


class CertificateSourceListResult(BaseModel):
    """Result of ``aeat config auth certificate list``."""

    model_config = _STRICT_FROZEN

    sources: tuple[CertificateSourcePayload, ...] = ()
    active_source: str = ""


class CertificateSourceMutationResult(BaseModel):
    """Result of registering, selecting, or removing a certificate source."""

    model_config = _STRICT_FROZEN

    name: str
    certificate_path: str = ""
    active: bool = False
    removed: bool = False


class CertificateSourceCheckEntry(BaseModel):
    """Expiry/rotation verdict for one registered certificate source.

    Reuses the same local PKCS#12 health classification
    :func:`application.auth.probe_provider_configuration` runs for the
    single-certificate provider path (``ok`` / ``expiring`` / ``expired`` /
    ``corrupt`` / ``unreadable`` / ``file_missing``), applied per named
    source in the ``certificate_sources`` registry on
    :class:`application.workflow.AuthState`
    rather than only the active ``certificate_path``. Never carries
    certificate passwords or key material.

    Attributes:
        name: The registered source name.
        certificate_path: Filesystem path of the source's PKCS#12 bundle.
        friendly_name: Optional human-readable label.
        active: Whether this source is the currently selected one.
        result: Typed :class:`application.auth.ProviderProbeResult` verdict
            (as its string value, matching the sibling ``AuthTestResult``
            convention).
        summary: Localised one-line operator-facing verdict.
        days_until_expiry: Whole days until ``not_after``, when the
            certificate could be parsed; negative when already expired;
            ``None`` when expiry could not be determined (unreadable,
            corrupt, missing path/file, or no configured decode password).
    """

    model_config = _STRICT_FROZEN

    name: str
    certificate_path: str
    friendly_name: str = ""
    active: bool = False
    result: str = ""
    summary: str = ""
    days_until_expiry: int | None = None


class CertificateSourceCheckReport(BaseModel):
    """Result of ``aeat config auth certificate check``.

    ``has_warnings`` is ``True`` when at least one entry's ``result`` is
    ``expiring`` or ``expired``, letting the CLI decide whether to attach
    a non-blocking rotation-reminder :class:`~core.json_contract.Notice`
    per entry without re-deriving the same predicate.
    """

    model_config = _STRICT_FROZEN

    entries: tuple[CertificateSourceCheckEntry, ...] = ()
    has_warnings: bool = False


class CertificateSourceSecretMutationResult(BaseModel):
    """Result of setting, rotating, or removing a named certificate source's secret.

    Never carries the secret value itself — only whether one is now
    registered and whether the call rotated an existing secret
    (``rotated``) or set one for the first time. Named certificate secrets
    have exactly one storage authority — encrypted secure storage — so no
    backend descriptor is reported. Mirrors the
    ``sensitive-financial-data-secure-storage-only`` and
    ``no-silent-under-declaration`` disciplines: the secret's *presence*
    is observable, its *value* never is.
    """

    model_config = _STRICT_FROZEN

    name: str
    has_secret: bool = False
    rotated: bool = False
    removed: bool = False


__all__ = [
    "AuthCleanupInProgressError",
    "AuthConfigureDanglingActiveProfileError",
    "AuthConfigureNoActiveBucketError",
    "AuthConfigureResult",
    "AuthLoginNotEnabledError",
    "AuthLoginPreconditionError",
    "AuthLoginResult",
    "AuthLogoutResult",
    "AuthOperationScopeConflictError",
    "AuthProviderNotConfiguredError",
    "AuthProviderReservedError",
    "AuthProvidersReport",
    "AuthResetResult",
    "AuthStatusResult",
    "AuthTestResult",
    "CertificateSecretMutationInProgressError",
    "CertificateSourceCheckEntry",
    "CertificateSourceCheckReport",
    "CertificateSourceListResult",
    "CertificateSourceMutationResult",
    "CertificateSourceNotFoundError",
    "CertificateSourcePayload",
    "CertificateSourceSecretMutationResult",
    "LiveAuthPreflightReport",
]
