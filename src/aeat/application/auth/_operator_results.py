"""Operator-facing auth result contracts.

These records project provider catalogue entries, readiness checks, live-login
results, and preflight state through :class:`AuthProvidersReport`,
:class:`AuthStatusResult`, :class:`AuthTestResult`, and
:class:`LiveAuthPreflightReport`.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import AeatError
from ._catalogue import AuthProviderListing


class AuthProviderReservedError(AeatError, ValueError):
    """Raised when a known provider slot is reserved but not implemented."""


class AuthConfigureNoActiveBucketError(AeatError):
    """Raised when auth configuration runs before an active profile bucket exists."""


class AuthConfigureDanglingActiveProfileError(AeatError, ValueError):
    """Raised when the active-profile pointer does not resolve to a registered bucket."""


class AuthLoginNotEnabledError(AeatError):
    """Raised when pytest invokes ``auth login`` without the live-test opt-in enabled."""


class AuthLoginPreconditionError(AeatError):
    """Raised when ``auth login`` cannot proceed because the configured provider is unusable."""


class AuthProvidersReport(BaseModel):
    """Auth provider catalogue projected for operator output."""

    model_config = _STRICT_FROZEN

    providers: tuple[AuthProviderListing, ...]


class AuthConfigureResult(BaseModel):
    """Result of configuring an auth provider in workflow state.

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
    """Current local auth readiness state."""

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
    """Redacted live-auth readiness report rendered before operator approval waits."""

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
    certificate_backend: str = ""
    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    persisted_session_state: str = ""
    probe_result: str = ""


class AuthLoginResult(BaseModel):
    """Result of an operator-triggered live authentication attempt."""

    model_config = _STRICT_FROZEN

    provider: str
    authenticated: bool
    reused_persisted_session: bool
    fresh: bool
    removed_sessions: int
    acquired_lock: bool
    reset_lock_state: str = ""
    verification_status: str = ""


class AuthClearResult(BaseModel):
    """Result of clearing local auth metadata and persisted state."""

    model_config = _STRICT_FROZEN

    removed_sessions: int
    cleared_workflow_state: bool
    cleared_locks: int


__all__ = [
    "AuthClearResult",
    "AuthConfigureDanglingActiveProfileError",
    "AuthConfigureNoActiveBucketError",
    "AuthConfigureResult",
    "AuthLoginNotEnabledError",
    "AuthLoginPreconditionError",
    "AuthLoginResult",
    "AuthProviderReservedError",
    "AuthProvidersReport",
    "AuthStatusResult",
    "AuthTestResult",
    "LiveAuthPreflightReport",
]
