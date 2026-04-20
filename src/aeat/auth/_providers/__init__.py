"""Provider-agnostic AEAT auth contracts.

The current runtime still authenticates with a certificate-backed
flow, but downstream consumers should depend on these abstractions
instead of hard-coding certificate-shaped session records.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ._certificate._certificate_backends._playwright_context import (
    build_client_certificates_kwarg,
)
from ._certificate.certificate import (
    HandshakeResult,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
)

if TYPE_CHECKING:
    from ...config import Settings
    from .._authenticator import (
        AeatLoginAssertion,
        AeatSession,
        BrowserContextLike,
        BrowserSessionFactory,
        BrowserSessionLike,
    )

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

CERTIFICATE_CONTEXT_MARKER = "_aeat_certificate_thumbprint"


class AuthProviderKind(StrEnum):
    """Closed catalogue of AEAT auth-provider identifiers."""

    CERTIFICATE = "certificate"
    CLAVE_PERMANENTE = "clave_permanente"
    CLAVE_MOVIL = "clave_movil"
    CLAVE_PIN = "clave_pin"


class AuthProviderDescription(BaseModel):
    """Safe, loggable description of one auth provider's current state."""

    model_config = _STRICT_FROZEN

    kind: AuthProviderKind
    label: str = Field(min_length=1)
    configured: bool
    available: bool
    identity_nif: str | None = None
    subject: str | None = None
    expires_on: date | None = None
    health_severity: str | None = None
    days_until_expiry: int | None = None
    health_summary: str | None = None


def describe_provider_operator_impact(description: AuthProviderDescription) -> str:
    """Explain what ``description`` means for Kent's CLI workflow today."""

    if not description.configured:
        return (
            "Kent can still produce, verify, and export filings locally, but "
            "AEAT-backed reads and live submit stay unavailable until an auth "
            "provider is configured."
        )
    if not description.available:
        return (
            f"{description.label} is configured but not ready yet. Kent can still "
            "produce, verify, and export filings locally, but AEAT-backed reads "
            "and live submit stay unavailable until auth is fixed."
        )
    if description.kind == AuthProviderKind.CERTIFICATE:
        return (
            "Certificate auth is ready. Kent keeps the same CLI filing flow for "
            "AEAT-backed reads, live submit remains separately gated, and future "
            "providers can plug into the same commands without changing the workflow."
        )
    return (
        f"{description.label} is ready. Kent keeps the same CLI filing flow while "
        "this provider plugs into the shared auth protocol."
    )


class CertificateSessionDetail(BaseModel):
    """Certificate-backed session details."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CERTIFICATE] = AuthProviderKind.CERTIFICATE
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    handshake: HandshakeResult


class ClavePermanenteSessionDetail(BaseModel):
    """Placeholder detail shape for future Cl@ve Permanente sessions."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CLAVE_PERMANENTE] = AuthProviderKind.CLAVE_PERMANENTE


class ClaveMovilSessionDetail(BaseModel):
    """Placeholder detail shape for future Cl@ve Movil sessions."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CLAVE_MOVIL] = AuthProviderKind.CLAVE_MOVIL


class ClavePinSessionDetail(BaseModel):
    """Placeholder detail shape for future Cl@ve PIN sessions."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CLAVE_PIN] = AuthProviderKind.CLAVE_PIN


class CertificateLoginAssertionDetail(BaseModel):
    """Certificate-backed verification details."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CERTIFICATE] = AuthProviderKind.CERTIFICATE
    handshake_success: bool
    certificate_recognised: bool
    parsed_subject: str | None = None


class ClavePermanenteLoginAssertionDetail(BaseModel):
    """Placeholder verification detail shape for future Cl@ve Permanente."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CLAVE_PERMANENTE] = AuthProviderKind.CLAVE_PERMANENTE


class ClaveMovilLoginAssertionDetail(BaseModel):
    """Placeholder verification detail shape for future Cl@ve Movil."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CLAVE_MOVIL] = AuthProviderKind.CLAVE_MOVIL


class ClavePinLoginAssertionDetail(BaseModel):
    """Placeholder verification detail shape for future Cl@ve PIN."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CLAVE_PIN] = AuthProviderKind.CLAVE_PIN


AuthSessionDetail = (
    CertificateSessionDetail | ClavePermanenteSessionDetail | ClaveMovilSessionDetail | ClavePinSessionDetail
)

AuthLoginAssertionDetail = (
    CertificateLoginAssertionDetail
    | ClavePermanenteLoginAssertionDetail
    | ClaveMovilLoginAssertionDetail
    | ClavePinLoginAssertionDetail
)


@runtime_checkable
class BrowserContextProvisioner(Protocol):
    """Hook that decorates BrowserSession.create_context()."""

    def build_context_kwargs(self) -> Mapping[str, Any]: ...

    def annotate_context(self, context: BrowserContextLike) -> None: ...


class CertificateContextProvisioner:
    """Browser-context provisioner for the certificate-backed auth flow."""

    def __init__(self, cert: LoadedCertificate, *, origin: str) -> None:
        self._cert = cert
        self._origin = origin

    def build_context_kwargs(self) -> Mapping[str, Any]:
        return {
            "client_certificates": build_client_certificates_kwarg(
                self._cert,
                self._origin,
            )
        }

    def annotate_context(self, context: BrowserContextLike) -> None:
        setattr(context, CERTIFICATE_CONTEXT_MARKER, self._cert.sha256_thumbprint)


@runtime_checkable
class AuthProvider(Protocol):
    """Provider-agnostic protocol for AEAT authentication."""

    kind: AuthProviderKind

    async def authenticate(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession: ...

    async def verify(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion: ...

    def describe(self) -> AuthProviderDescription: ...


def describe_certificate_provider(
    cert: LoadedCertificate,
    *,
    warn_days: int,
    critical_days: int,
) -> AuthProviderDescription:
    """Build an :class:`AuthProviderDescription` from a loaded certificate."""

    health = evaluate_loaded_certificate_health(
        cert,
        warn_days=warn_days,
        critical_days=critical_days,
    )
    try:
        identity_nif = extract_nif_from_subject(cert)
    except Exception:
        identity_nif = None
    return AuthProviderDescription(
        kind=AuthProviderKind.CERTIFICATE,
        label="AEAT certificate",
        configured=True,
        available=True,
        identity_nif=identity_nif,
        subject=cert.subject,
        expires_on=cert.not_after.date(),
        health_severity=health.severity.value,
        days_until_expiry=health.days_until_expiry,
        health_summary=f"{health.severity.value}:{health.days_until_expiry}",
    )


def select_provider(
    kind: AuthProviderKind,
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactory | None = None,
) -> AuthProvider:
    """Return the configured auth-provider implementation for ``kind``."""

    if kind is AuthProviderKind.CERTIFICATE:
        from .._authenticator import AeatAuthenticator

        return AeatAuthenticator(
            settings,
            browser_session_factory=browser_session_factory,
        )
    raise NotImplementedError(f"auth provider {kind.value!r} is not implemented yet")


__all__ = [
    "CERTIFICATE_CONTEXT_MARKER",
    "AuthLoginAssertionDetail",
    "AuthProvider",
    "AuthProviderDescription",
    "AuthProviderKind",
    "AuthSessionDetail",
    "BrowserContextProvisioner",
    "CertificateContextProvisioner",
    "CertificateLoginAssertionDetail",
    "CertificateSessionDetail",
    "ClaveMovilLoginAssertionDetail",
    "ClaveMovilSessionDetail",
    "ClavePermanenteLoginAssertionDetail",
    "ClavePermanenteSessionDetail",
    "ClavePinLoginAssertionDetail",
    "ClavePinSessionDetail",
    "describe_certificate_provider",
    "describe_provider_operator_impact",
    "select_provider",
]
