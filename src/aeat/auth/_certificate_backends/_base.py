"""Abstract base class for certificate backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..certificate import HandshakeResult, LoadedCertificate


class _CertBackend(ABC):
    """Contract every cert backend must satisfy.

    Backends are dispatched by
    :func:`aeat.auth.certificate._select_backend` and consumed by
    :func:`aeat.auth.certificate.preload_into_browser_context` and
    :func:`aeat.auth.certificate.verify_handshake`.
    """

    @abstractmethod
    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        """Validate that ``context`` is configured for ``cert``.

        Raises:
            aeat.auth.certificate.CertificateError: When the backend
                rejects the context or cannot enforce the contract.
        """

    @abstractmethod
    def verify(self, cert: LoadedCertificate, url: str) -> HandshakeResult:
        """Perform an mTLS handshake smoke test against ``url``."""
