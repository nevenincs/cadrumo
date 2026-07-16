"""Provider-specific AEAT session details and context provisioners.

:class:`core.AuthProviderKind` and :class:`core.AuthProviderDescription` are
the layer-neutral provider authorities. :class:`application.auth.AuthProvider`
is the application protocol, and
:func:`core.i18n.describe_auth_provider_operator_impact` is the canonical
localized renderer. This module owns only the provider-specific payloads
used by :class:`adapters.outbound.aeat.auth.AeatSession` and
:class:`adapters.outbound.aeat.auth.AeatLoginAssertion`, plus the
certificate browser-context provisioner that wires PKCS#12 credentials into
Playwright contexts.
"""

from __future__ import annotations

from typing import Literal, Protocol, TypedDict, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core import AuthProviderDescription as _AuthProviderDescription
from .....core import AuthProviderKind as _AuthProviderKind
from .....core.config import (
    AEAT_CERTIFICATE_PROTECTED_ORIGIN,
    AEAT_CERTIFICATE_PROTECTED_URL,
)
from .certificate import (
    CertificateNifParseError,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
)


class CertificateSessionDetail(BaseModel):
    """Certificate-specific detail embedded in an authenticated AEAT session.

    :class:`adapters.outbound.aeat.auth.AeatAuthenticator` populates this
    detail for certificate-backed :class:`adapters.outbound.aeat.auth.AeatSession`
    records. The thumbprint and subject bind the live session to the loaded
    certificate. ``protected_resource_url`` records the sole accepted browser
    proof used to establish the session.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[_AuthProviderKind.CERTIFICATE] = _AuthProviderKind.CERTIFICATE
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    protected_resource_url: str = AEAT_CERTIFICATE_PROTECTED_URL

    @field_validator("protected_resource_url")
    @classmethod
    def _protected_resource_is_canonical(cls, value: str) -> str:
        if value != AEAT_CERTIFICATE_PROTECTED_URL:
            raise ValueError("certificate session proof must use the canonical protected resource")
        return value


class ClaveMovilSessionDetail(BaseModel):
    """Detail shape for a Cl@ve Móvil-authenticated AEAT session.

    :class:`adapters.outbound.aeat.auth.ClaveMovilAuthProvider` projects
    :class:`adapters.outbound.aeat.auth._clave_movil_metadata.ClaveMovilSessionMetadata`
    into this detail when fresh or persisted Cl@ve sessions become
    :class:`adapters.outbound.aeat.auth.AeatSession` records. The session
    does not carry long-lived credential material; the cookie set in encrypted
    browser storage remains the authority for reuse.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[_AuthProviderKind.CLAVE_MOVIL] = _AuthProviderKind.CLAVE_MOVIL
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


class ClavePermanenteSessionDetail(BaseModel):
    """Detail shape for a Cl@ve Permanente-authenticated AEAT session.

    :class:`adapters.outbound.aeat.auth.ClavePermanenteAuthProvider`
    populates this detail for DNI/NIE + password logins. Unlike Cl@ve Móvil,
    the flow carries no verification code and no phone-approval state — the
    login form is fully headless-automatable for AEAT read paths.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[_AuthProviderKind.CLAVE_PERMANENTE] = _AuthProviderKind.CLAVE_PERMANENTE
    dni_nie: str = Field(
        min_length=1,
        description="DNI/NIE used as the Cl@ve Permanente login username (authoritative identity).",
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

    Carries the observed final URL and certificate subject from the canonical
    protected-resource browser probe.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[_AuthProviderKind.CERTIFICATE] = _AuthProviderKind.CERTIFICATE
    final_url: str | None = None
    response_successful: bool
    parsed_subject: str | None = None


class ClaveMovilLoginAssertionDetail(BaseModel):
    """Verification detail for a Cl@ve Móvil-backed session probe.

    After a successful Cl@ve Móvil login, the provider probes an AEAT Sede page
    to confirm that the session cookies are still live. This detail records the
    cookie and landing-URL signals carried by
    :class:`adapters.outbound.aeat.auth.AeatLoginAssertion`.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[_AuthProviderKind.CLAVE_MOVIL] = _AuthProviderKind.CLAVE_MOVIL
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


class ClavePermanenteLoginAssertionDetail(BaseModel):
    """Verification detail for a Cl@ve Permanente-backed session probe.

    After a successful Cl@ve Permanente login, the provider probes an AEAT
    Sede page to confirm the session cookies are still live. This detail
    records the cookie and landing-URL signals carried by
    :class:`adapters.outbound.aeat.auth.AeatLoginAssertion`.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[_AuthProviderKind.CLAVE_PERMANENTE] = _AuthProviderKind.CLAVE_PERMANENTE
    session_cookie_present: bool = Field(
        default=False,
        description=(
            "True when the probe response carried an AEAT session cookie; "
            "primary signal that Cl@ve Permanente login is still live."
        ),
    )
    landing_url: str | None = Field(
        default=None,
        description="Final URL Playwright landed on after following redirects.",
    )


AuthSessionDetail = CertificateSessionDetail | ClaveMovilSessionDetail | ClavePermanenteSessionDetail

AuthLoginAssertionDetail = (
    CertificateLoginAssertionDetail | ClaveMovilLoginAssertionDetail | ClavePermanenteLoginAssertionDetail
)


class BrowserContextKwargs(TypedDict, total=False):
    """Subset of Playwright ``Browser.new_context()`` keyword arguments.

    Only the kwargs that AEAT auth provisioners currently supply are
    declared here. ``total=False`` makes every key optional so callers
    can return a partial mapping.
    """

    client_certificates: list[dict[str, str]]


@runtime_checkable
class BrowserContextProvisioner(Protocol):
    """Hook that decorates browser-context creation for auth providers.

    :class:`CertificateContextProvisioner` implements this protocol to add
    Playwright ``new_context()`` kwargs.
    """

    def build_context_kwargs(self) -> BrowserContextKwargs: ...


class CertificateContextProvisioner:
    """Browser-context provisioner for the certificate-backed AEAT auth flow.

    Implements :class:`BrowserContextProvisioner` for PKCS#12 client-certificate
    authentication. ``build_context_kwargs`` wires the loaded certificate into
    Playwright's ``client_certificates`` list so every TLS connection the
    browser makes to the AEAT origin presents the certificate automatically.
    The provisioner contributes only the Playwright client-certificate
    construction argument. Authentication is proved by the subsequent
    canonical protected-resource navigation, never by a context marker.
    """

    def __init__(self, cert: LoadedCertificate) -> None:
        """Bind ``cert`` to the canonical AEAT certificate origin.

        Args:
            cert: The :class:`~adapters.outbound.aeat.auth.certificate.LoadedCertificate`
                whose PKCS#12 bytes will be presented to the AEAT origin.
        """
        self._cert = cert

    def build_context_kwargs(self) -> BrowserContextKwargs:
        """Return the Playwright ``new_context()`` kwargs that wire the certificate.

        Returns:
            A :class:`BrowserContextKwargs` mapping with ``client_certificates``
            populated for the bound origin.
        """
        return {
            "client_certificates": [
                {
                    "origin": AEAT_CERTIFICATE_PROTECTED_ORIGIN,
                    "pfxPath": str(self._cert.source_path),
                    "passphrase": self._cert._password.get_secret_value(),
                },
            ],
        }


def describe_certificate_provider(
    cert: LoadedCertificate,
    *,
    warn_days: int,
    critical_days: int,
) -> _AuthProviderDescription:
    """Build an :class:`AuthProviderDescription` from a loaded certificate.

    The returned description carries the parsed identity NIF when available and
    the :class:`~adapters.outbound.aeat.auth.certificate.CertificateHealth`
    severity used by operator-facing auth status commands.
    """
    health = evaluate_loaded_certificate_health(
        cert,
        warn_days=warn_days,
        critical_days=critical_days,
    )
    try:
        identity_nif = extract_nif_from_subject(cert)
    except CertificateNifParseError:
        identity_nif = None
    return _AuthProviderDescription(
        kind=_AuthProviderKind.CERTIFICATE,
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
    "AuthLoginAssertionDetail",
    "AuthSessionDetail",
    "BrowserContextProvisioner",
    "CertificateContextProvisioner",
    "CertificateLoginAssertionDetail",
    "CertificateSessionDetail",
    "ClaveMovilLoginAssertionDetail",
    "ClaveMovilSessionDetail",
    "ClavePermanenteLoginAssertionDetail",
    "ClavePermanenteSessionDetail",
    "describe_certificate_provider",
]
