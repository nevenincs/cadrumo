"""Build the authentication sub-projection for operator state.

The public facade remains :mod:`cadrumo.application.state_projection`; this
private module is its internal authentication producer. It derives redacted,
fail-closed readiness from either an active-auth snapshot or direct state.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core import AuthProviderKind
from ..core.config import load_settings
from ..core.errors import CadrumoError
from ..core.logging import get_logger
from .auth import (
    probe_provider_credentials,
    project_active_certificate_credentials,
    select_provider,
)
from .auth_credentials import ActiveCertificateCredentials
from .workflow import WorkflowState

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
    probe_result: str = ""
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
    if provider_kind_is_authoritative:
        provider = provider_kind.value if provider_kind is not None else ""
    else:
        normalized_request = requested_provider.strip().lower() if requested_provider is not None else None
        provider_selector = normalized_request or auth.provider or ""
        try:
            provider_kind = AuthProviderKind(provider_selector) if provider_selector else None
        except ValueError:
            provider_kind = None
        provider = provider_kind.value if provider_kind is not None else ""

    effective_certificate_path = auth.certificate_path or ""
    backend_settings = None
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
    configured = _provider_configured(
        state,
        provider_kind=provider_kind,
        effective_certificate_path=effective_certificate_path,
    )

    available = configured and bool(auth.authenticated_at)
    health_summary = ""
    health_severity = ""
    probe_result = ""
    probe_summary = ""
    if probe_live_backend and provider_kind is None and requested_provider is not None and requested_provider.strip():
        _log.warning(
            "auth backend probe skipped for unknown provider; reporting unavailable",
        )
    if probe_live_backend and provider_kind is not None:
        if credential_bucket_id is None:
            available = False
        else:
            try:
                if backend_settings is None:
                    backend_settings = load_settings()
                backend = select_provider(
                    provider_kind,
                    settings=backend_settings,
                    certificate_credentials=certificate_credentials,
                )
                description = backend.describe()
                available = description.available
                health_summary = description.health_summary or ""
                health_severity = description.health_severity or ""
                configured = configured and description.configured
            except (CadrumoError, OSError, ValueError, AttributeError):
                _log.warning(
                    "auth backend probe failed; reporting unavailable",
                    exc_info=True,
                )
                available = False
    if probe_live_backend and credential_bucket_id is not None:
        provider_probe = probe_provider_credentials(
            provider,
            effective_certificate_path,
            settings=backend_settings,
            certificate_credentials=certificate_credentials,
        )
        probe_result = str(provider_probe.result)
        probe_summary = provider_probe.summary

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
