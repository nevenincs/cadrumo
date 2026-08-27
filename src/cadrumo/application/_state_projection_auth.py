"""Build the authentication sub-projection for operator state.

The public facade remains :mod:`cadrumo.application.state_projection`; this
private module is its internal authentication producer. It derives redacted,
fail-closed readiness from either an active-auth snapshot or direct state.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel

from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core import AuthProviderKind
from ..core.config import Settings, load_settings
from ..core.errors import CadrumoError
from ..core.logging import get_logger
from .auth.credentials import project_active_certificate_credentials
from .auth.operator_probes import bind_profile_auth_settings, probe_provider_credentials
from .auth.probes import ProviderProbeResult
from .auth.providers import select_provider
from .auth_credentials import ActiveCertificateCredentials
from .workflow.state_models import WorkflowState

_log = get_logger(__name__)


class ProjectionAuthReadiness(BaseModel):
    """Redacted authentication readiness with route provenance.

    A provider is configured only when its typed value exactly matches the
    persisted selector; the certificate provider additionally requires its
    effective path to exist. Invalid selectors remain unconfigured and are
    never exposed through projection output. A backend probe may downgrade
    configuration and supplies only the health and probe fields.
    """

    model_config = _STRICT_FROZEN

    provider: str = ""
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    health_summary: str = ""
    health_severity: str = ""
    certificate_path: str = ""
    probe_result: ProviderProbeResult | None = None
    probe_summary: str = ""


def _certificate_path_resolves(certificate_path: str) -> bool:
    """Return whether a recorded certificate path resolves to an existing file."""
    if not certificate_path:
        return False
    try:
        return Path(certificate_path).is_file()
    except OSError:
        return False


def _provider_configured(
    state: WorkflowState,
    *,
    provider_kind: AuthProviderKind | None,
    effective_certificate_path: str,
) -> bool:
    """Return whether the typed provider exactly matches usable persisted state.

    Certificate state additionally requires an existing effective certificate
    path. Missing, mismatched, or invalid selectors fail closed.
    """
    auth = state.auth
    if provider_kind is None or auth.provider != provider_kind.value:
        return False
    if provider_kind is AuthProviderKind.CERTIFICATE:
        return _certificate_path_resolves(effective_certificate_path)
    return True


def _resolve_provider_selection(
    state: WorkflowState,
    *,
    provider_kind: AuthProviderKind | None,
    provider_kind_is_authoritative: bool,
    requested_provider: str | None,
) -> tuple[AuthProviderKind | None, str]:
    """Resolve the effective provider kind and its redacted label.

    An authoritative kind passes through unchanged. Otherwise the requested
    provider (normalized) or the persisted selector is parsed, failing closed
    to ``None`` on an invalid selector without exposing its raw value.
    """
    if provider_kind_is_authoritative:
        return provider_kind, (provider_kind.value if provider_kind is not None else "")
    normalized_request = requested_provider.strip().lower() if requested_provider is not None else None
    provider_selector = normalized_request or state.auth.provider or ""
    try:
        resolved_kind = AuthProviderKind(provider_selector) if provider_selector else None
    except ValueError:
        resolved_kind = None
    return resolved_kind, (resolved_kind.value if resolved_kind is not None else "")


class _CertificateResolution(NamedTuple):
    effective_certificate_path: str
    backend_settings: Settings | None
    certificate_credentials: ActiveCertificateCredentials | None


def _resolve_certificate_context(
    state: WorkflowState,
    *,
    provider_kind: AuthProviderKind | None,
    certificate_credentials: ActiveCertificateCredentials | None,
) -> _CertificateResolution:
    """Load settings and project certificate credentials only for the certificate kind."""
    effective_certificate_path = state.auth.certificate_path or ""
    backend_settings: Settings | None = None
    if provider_kind is AuthProviderKind.CERTIFICATE:
        backend_settings = load_settings()
        if certificate_credentials is None:
            certificate_credentials = project_active_certificate_credentials(
                state,
                settings=backend_settings,
            )
        effective_certificate_path = (
            str(certificate_credentials.certificate_path)
            if certificate_credentials.certificate_path is not None
            else ""
        )
    return _CertificateResolution(
        effective_certificate_path=effective_certificate_path,
        backend_settings=backend_settings,
        certificate_credentials=certificate_credentials,
    )


class _BackendProbeOutcome(NamedTuple):
    configured: bool
    available: bool
    health_summary: str
    health_severity: str
    backend_settings: Settings | None


def _describe_backend_health(
    *,
    provider_kind: AuthProviderKind,
    configured: bool,
    backend_settings: Settings | None,
    certificate_credentials: ActiveCertificateCredentials | None,
) -> _BackendProbeOutcome:
    """Describe the selected backend, lowering ``configured`` and never elevating it.

    Any load / selection / description failure is logged and reported as
    unavailable. Settings are lazily loaded when absent.
    """
    try:
        if backend_settings is None:
            backend_settings = load_settings()
        backend = select_provider(
            provider_kind,
            settings=backend_settings,
            certificate_credentials=certificate_credentials,
        )
        description = backend.describe()
        return _BackendProbeOutcome(
            configured=configured and description.configured,
            available=description.available,
            health_summary=description.health_summary or "",
            health_severity=description.health_severity or "",
            backend_settings=backend_settings,
        )
    except (CadrumoError, OSError, ValueError, AttributeError):
        _log.warning(
            "auth backend probe failed; reporting unavailable",
            exc_info=True,
        )
        return _BackendProbeOutcome(
            configured=configured,
            available=False,
            health_summary="",
            health_severity="",
            backend_settings=backend_settings,
        )


def _probe_backend_readiness(
    *,
    provider_kind: AuthProviderKind | None,
    requested_provider: str | None,
    configured: bool,
    available: bool,
    credential_bucket_id: str | None,
    backend_settings: Settings | None,
    certificate_credentials: ActiveCertificateCredentials | None,
) -> _BackendProbeOutcome:
    """Probe the live backend, downgrading readiness only.

    An unknown requested provider is warned and left unavailable; a selected
    provider with no credential bucket is downgraded to unavailable; otherwise
    the backend description supplies health and may only lower ``configured``.
    """
    if provider_kind is None:
        if requested_provider is not None and requested_provider.strip():
            _log.warning(
                "auth backend probe skipped for unknown provider; reporting unavailable",
            )
        return _BackendProbeOutcome(configured, available, "", "", backend_settings)
    if credential_bucket_id is None:
        return _BackendProbeOutcome(configured, False, "", "", backend_settings)
    return _describe_backend_health(
        provider_kind=provider_kind,
        configured=configured,
        backend_settings=backend_settings,
        certificate_credentials=certificate_credentials,
    )


def _probe_credentials(
    *,
    provider: str,
    effective_certificate_path: str,
    backend_settings: Settings | None,
    certificate_credentials: ActiveCertificateCredentials | None,
) -> tuple[ProviderProbeResult, str]:
    """Probe provider credentials, returning ``(probe_result, probe_summary)``."""
    provider_probe = probe_provider_credentials(
        provider,
        effective_certificate_path,
        settings=backend_settings,
        certificate_credentials=certificate_credentials,
    )
    return provider_probe.result, provider_probe.summary


def build_auth_readiness(
    state: WorkflowState,
    *,
    provider_kind: AuthProviderKind | None,
    provider_kind_is_authoritative: bool,
    requested_provider: str | None,
    probe_live_backend: bool,
    credential_bucket_id: str | None,
    certificate_credentials: ActiveCertificateCredentials | None,
) -> ProjectionAuthReadiness:
    """Build redacted authentication readiness from a snapshot or direct state.

    Snapshot-backed and direct-state paths enforce the same exact-match and
    existing-certificate rule. Invalid selectors fail closed without exposing
    their raw value. Snapshot credentials retain their witnessed storage route;
    direct state cannot borrow one. A backend probe may downgrade configured
    readiness, but never elevate it.
    """
    auth = state.auth
    provider_kind, provider = _resolve_provider_selection(
        state,
        provider_kind=provider_kind,
        provider_kind_is_authoritative=provider_kind_is_authoritative,
        requested_provider=requested_provider,
    )
    certificate = _resolve_certificate_context(
        state,
        provider_kind=provider_kind,
        certificate_credentials=certificate_credentials,
    )
    effective_certificate_path = certificate.effective_certificate_path
    backend_settings = certificate.backend_settings
    certificate_credentials = certificate.certificate_credentials

    if probe_live_backend and provider_kind in (
        AuthProviderKind.CLAVE_MOVIL,
        AuthProviderKind.CLAVE_PERMANENTE,
    ):
        backend_settings = bind_profile_auth_settings(
            provider_kind,
            settings=load_settings(),
            state=state,
        )

    configured = _provider_configured(
        state,
        provider_kind=provider_kind,
        effective_certificate_path=effective_certificate_path,
    )

    available = configured and bool(auth.authenticated_at)
    health_summary = ""
    health_severity = ""
    probe_result: ProviderProbeResult | None = None
    probe_summary = ""
    if probe_live_backend:
        probe = _probe_backend_readiness(
            provider_kind=provider_kind,
            requested_provider=requested_provider,
            configured=configured,
            available=available,
            credential_bucket_id=credential_bucket_id,
            backend_settings=backend_settings,
            certificate_credentials=certificate_credentials,
        )
        configured = probe.configured
        available = probe.available
        health_summary = probe.health_summary
        health_severity = probe.health_severity
        backend_settings = probe.backend_settings
    if probe_live_backend and credential_bucket_id is not None:
        probe_result, probe_summary = _probe_credentials(
            provider=provider,
            effective_certificate_path=effective_certificate_path,
            backend_settings=backend_settings,
            certificate_credentials=certificate_credentials,
        )

    authenticated = configured and bool(auth.authenticated_at)
    health_severity = _resolve_health_severity(
        health_severity,
        provider=provider,
        configured=configured,
        available=available,
        authenticated=authenticated,
    )

    return ProjectionAuthReadiness(
        provider=provider,
        configured=configured,
        authenticated=authenticated,
        available=available,
        health_summary=health_summary,
        health_severity=health_severity,
        certificate_path=(effective_certificate_path if provider_kind is AuthProviderKind.CERTIFICATE else ""),
        probe_result=probe_result,
        probe_summary=probe_summary,
    )


def _resolve_health_severity(
    backend_severity: str,
    *,
    provider: str,
    configured: bool,
    available: bool,
    authenticated: bool,
) -> str:
    """Resolve health severity without elevating authentication readiness.

    A non-empty backend severity is preserved. Otherwise, no selected provider
    yields an empty severity; a selected but unconfigured provider yields
    ``"info"``; configured, available, and authenticated readiness yields
    ``"ok"``; every other selected/configured state yields ``"warning"``.
    """
    if backend_severity:
        return backend_severity
    if not provider:
        return ""
    if not configured:
        return "info"
    if available and authenticated:
        return "ok"
    return "warning"
