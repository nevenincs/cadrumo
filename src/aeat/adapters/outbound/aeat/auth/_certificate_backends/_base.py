"""Abstract contract for certificate backends.

Defines :class:`_CertBackend`, the interface every concrete backend
under :mod:`aeat.adapters.outbound.aeat.auth._certificate_backends`
must implement. Backends are dispatched by
:func:`aeat.adapters.outbound.aeat.auth.certificate._select_backend`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..certificate import HandshakeResult, LoadedCertificate


class _CertBackend(ABC):
    """Contract every cert backend must satisfy.

    Backends are dispatched by
    :func:`aeat.adapters.outbound.aeat.auth.certificate._select_backend` and consumed by
    :func:`aeat.adapters.outbound.aeat.auth.certificate.preload_into_browser_context` and
    :func:`aeat.adapters.outbound.aeat.auth.certificate.verify_handshake`.
    """

    @abstractmethod
    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        """Validate that ``context`` is configured for ``cert``.

        Raises:
            aeat.adapters.outbound.aeat.auth.certificate.CertificateError: When the backend
                rejects the context or cannot enforce the contract.
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
