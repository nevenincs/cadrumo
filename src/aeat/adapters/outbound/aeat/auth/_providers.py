"""Concrete AEAT auth provider types and context provisioners.

Provider-agnostic abstractions (``AuthProviderKind``, ``AuthProviderDescription``,
``AuthProvider`` protocol, ``describe_provider_operator_impact``)
live in ``aeat.application.auth``; this module holds concrete
per-provider detail models and the certificate browser-context provisioner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, TypedDict, runtime_checkable

from pydantic import BaseModel, Field

from .....application.auth import (
    AuthProvider,
    AuthProviderDescription,
    AuthProviderKind,
    describe_provider_operator_impact,
)
from ._certificate_backends._base import CERTIFICATE_CONTEXT_MARKER
from ._certificate_backends._playwright_context import build_client_certificates_kwarg
from .certificate import (
    CertificateNifParseError,
    HandshakeResult,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
)

if TYPE_CHECKING:
    from ._authenticator import (
        BrowserContextLike,
    )

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class CertificateSessionDetail(BaseModel):
    """Certificate-backed session details."""

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CERTIFICATE] = AuthProviderKind.CERTIFICATE
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    handshake: HandshakeResult


class ClaveMovilSessionDetail(BaseModel):
    """Detail shape for a Cl@ve Móvil-authenticated AEAT session.

    Cl@ve Móvil hands AEAT a uniform set of session cookies after the
    user approves the push notification on their phone. The session
    does not carry any long-lived credential material — only the
    identity used during login and a rendezvous timestamp. The real
    authority is the cookie set persisted with the provider metadata in
    the encrypted session object.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CLAVE_MOVIL] = AuthProviderKind.CLAVE_MOVIL
    dni_nie: str = Field(
        min_length=1,
        description="DNI/NIE used for the login (authoritative identity).",
    )
    used_non_qr_fallback: bool = Field(
        default=False,
        description="True when the DNI/NIE + contraste fallback form was used rather than the QR code.",
    )
    verification_code: str | None = Field(
        default=None,
        description=(
            "Three-letter confirmation code shown on the AEAT QR page at "
            "login; recorded for audit only. Not reused on resume."
        ),
    )
    landing_url: str | None = Field(
        default=None,
        description=(
            "Concrete authenticated AEAT URL observed after login. "
            "Used by live verification and resume probes so the provider "
            "does not re-enter the auth selector when a session is already live."
        ),
    )


class CertificateLoginAssertionDetail(BaseModel):
    """Login-assertion detail for certificate-backed AEAT verification.

    Carries the three signals the authenticator collects during the
    post-auth navigation probe: whether the mTLS handshake leg
    succeeded, whether the AEAT sede (electronic office) returned a
    non-challenge HTTP response, and the RFC-4514 subject DN of the
    presented certificate.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CERTIFICATE] = AuthProviderKind.CERTIFICATE
    handshake_success: bool
    certificate_recognised: bool
    parsed_subject: str | None = None


class ClaveMovilLoginAssertionDetail(BaseModel):
    """Verification detail for a Cl@ve Móvil-backed session probe.

    After a successful Cl@ve Móvil login, the authenticator probes a
    well-known AEAT Sede URL to confirm that the session cookies are
    still live. This detail record carries the observed signals for
    that probe.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[AuthProviderKind.CLAVE_MOVIL] = AuthProviderKind.CLAVE_MOVIL
    session_cookie_present: bool = Field(
        default=False,
        description=(
            "True when the probe response carried an AEAT session cookie; "
            "primary signal that Cl@ve Móvil login is still live."
        ),
    )
    landing_url: str | None = Field(
        default=None,
        description="Final URL Playwright landed on after following redirects.",
    )


AuthSessionDetail = CertificateSessionDetail | ClaveMovilSessionDetail

AuthLoginAssertionDetail = CertificateLoginAssertionDetail | ClaveMovilLoginAssertionDetail


class BrowserContextKwargs(TypedDict, total=False):
    """Subset of Playwright ``Browser.new_context()`` keyword arguments.

    Only the kwargs that AEAT auth provisioners currently supply are
    declared here. ``total=False`` makes every key optional so callers
    can return a partial mapping.
    """

    client_certificates: list[dict[str, str]]


@runtime_checkable
class BrowserContextProvisioner(Protocol):
    """Hook that decorates BrowserSession.create_context()."""

    def build_context_kwargs(self) -> BrowserContextKwargs: ...

    def annotate_context(self, context: BrowserContextLike) -> None: ...


class CertificateContextProvisioner:
    """Browser-context provisioner for the certificate-backed AEAT auth flow.

    Implements :class:`BrowserContextProvisioner` for PKCS#12 client-certificate
    authentication. ``build_context_kwargs`` wires the loaded certificate into
    Playwright's ``client_certificates`` list so every TLS connection the
    browser makes to the AEAT origin presents the certificate automatically.
    ``annotate_context`` stamps the SHA-256 thumbprint of the certificate
    onto the context object as a marker attribute so the authenticator can
    confirm that the context was provisioned with the expected certificate.
    """

    def __init__(self, cert: LoadedCertificate, *, origin: str) -> None:
        """Bind ``cert`` to ``origin`` for context provisioning.

        Args:
            cert: The :class:`~aeat.adapters.outbound.aeat.auth.certificate.LoadedCertificate`
                whose PKCS#12 bytes will be presented to the AEAT origin.
            origin: URL origin (scheme + host) the certificate is valid for,
                passed to Playwright's ``client_certificates`` list as the
                binding scope.
        """
        self._cert = cert
        self._origin = origin

    def build_context_kwargs(self) -> BrowserContextKwargs:
        """Return the Playwright ``new_context()`` kwargs that wire the certificate.

        Returns:
            A :class:`BrowserContextKwargs` mapping with ``client_certificates``
            populated for the bound origin.
        """
        return {
            "client_certificates": build_client_certificates_kwarg(
                self._cert,
                self._origin,
            ),
        }

    def annotate_context(self, context: BrowserContextLike) -> None:
        """Stamp the certificate thumbprint onto ``context`` as a marker attribute.

        The marker attribute name is ``CERTIFICATE_CONTEXT_MARKER``. The
        authenticator reads this attribute after context creation to assert
        that the context was provisioned with the expected certificate.

        Args:
            context: The newly created :class:`~aeat.adapters.outbound.aeat.auth._authenticator.BrowserContextLike`
                to annotate.
        """
        setattr(context, CERTIFICATE_CONTEXT_MARKER, self._cert.sha256_thumbprint)


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
    except CertificateNifParseError:
        identity_nif = None
    return AuthProviderDescription(
        kind=AuthProviderKind.CERTIFICATE,
        label="AEAT certificate",
        configured=True,
        available=True,
        identity_nif=identity_nif,
        subject=cert.subject,
        expires_on=cert.not_after,
        health_severity=health.severity.value,
        days_until_expiry=health.days_until_expiry,
        health_summary=f"{health.severity.value}:{health.days_until_expiry}",
    )


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
    "describe_certificate_provider",
    "describe_provider_operator_impact",
]
