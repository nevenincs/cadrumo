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

from typing import Protocol, TypedDict, runtime_checkable

from .....core.auth_provider import AuthProviderDescription as _AuthProviderDescription
from .....core.auth_provider import AuthProviderKind as _AuthProviderKind
from .....core.config import AEAT_CERTIFICATE_PROTECTED_ORIGIN
from .certificate import (
    CertificateNifParseError,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
)


class BrowserContextKwargs(TypedDict, total=False):
    """Subset of Playwright ``Browser.new_context()`` keyword arguments.

    Only the kwargs that AEAT auth provisioners currently supply are
    declared here. ``total=False`` makes every key optional so callers
    can return a partial mapping.
    """

    client_certificates: list[dict[str, str | bytes]]


@runtime_checkable
class BrowserContextProvisioner(Protocol):
    """Hook that decorates browser-context creation for auth providers.

    :class:`CertificateContextProvisioner` implements this protocol to add
    Playwright ``new_context()`` kwargs.
    """

    def build_context_kwargs(self) -> BrowserContextKwargs:
        """Return the provider-owned browser context arguments."""
        ...


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
        pfx, passphrase = self._cert.client_certificate_material()
        return {
            "client_certificates": [
                {
                    "origin": AEAT_CERTIFICATE_PROTECTED_ORIGIN,
                    "pfx": pfx,
                    "passphrase": passphrase,
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
    "BrowserContextProvisioner",
    "CertificateContextProvisioner",
    "describe_certificate_provider",
]
