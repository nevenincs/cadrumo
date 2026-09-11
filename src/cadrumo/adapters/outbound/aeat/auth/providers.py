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

from .....application.auth.protocols import BrowserContextKwargs
from .....core.config_support import AEAT_CERTIFICATE_PROTECTED_ORIGIN
from .certificate import (
    LoadedCertificate,
)


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


__all__ = [
    "CertificateContextProvisioner",
]
