"""Abstract contract for certificate backend implementations.

Defines :class:`_CertBackend`, the interface every concrete backend under
:mod:`aeat.adapters.outbound.aeat.auth._certificate_backends` must implement.
Backends are selected from :class:`CertificateBackend` by
:func:`aeat.adapters.outbound.aeat.auth.certificate._select_backend` and feed
the public :func:`aeat.adapters.outbound.aeat.auth.certificate.preload_into_browser_context`
and :func:`aeat.adapters.outbound.aeat.auth.certificate.verify_handshake`
helpers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..certificate import HandshakeResult, LoadedCertificate


CERTIFICATE_CONTEXT_MARKER = "_aeat_certificate_thumbprint"
"""Attribute name a Playwright context carries after certificate provisioning.

The :class:`aeat.adapters.outbound.aeat.auth.CertificateContextProvisioner`
stamps the context with this attribute set to the
:class:`LoadedCertificate` thumbprint. The Playwright backend reads it during
``preload`` to verify that the context was provisioned correctly. Both
producer and consumer share this single source of truth.
"""


class _CertBackend(ABC):
    """Contract every cert backend must satisfy.

    Concrete backends validate a :class:`LoadedCertificate` against a browser
    context and return :class:`HandshakeResult` records for mTLS smoke probes.
    The public certificate module owns dispatch; this class only fixes the
    backend shape.
    """

    @abstractmethod
    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        """Validate that ``context`` is configured for ``cert``.

        Args:
            cert: The loaded PKCS#12 certificate to validate against.
            context: The browser or HTTP context to check.

        Raises:
            CertificateError: When the backend rejects the context or cannot enforce the contract.
        """

    @abstractmethod
    def verify(self, cert: LoadedCertificate, url: str) -> HandshakeResult:
        """Perform an mTLS handshake smoke test against ``url``.

        Args:
            cert: The loaded PKCS#12 certificate to present.
            url: HTTPS endpoint to probe with the client certificate.

        Returns:
            A :class:`aeat.adapters.outbound.aeat.auth.certificate.HandshakeResult`
            describing whether the handshake succeeded along with the
            observed status code, elapsed time, and any error message.
        """
