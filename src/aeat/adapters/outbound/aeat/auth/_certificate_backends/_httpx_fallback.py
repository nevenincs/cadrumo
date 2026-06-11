"""httpx-based mTLS handshake backend placeholder.

The Python :mod:`ssl` API used by :mod:`httpx` requires certificate-chain
material to be loaded from file paths. Writing decrypted PEM/key material to
temporary files violates the secure-storage boundary, so this backend fails
closed instead of materialising certificate secrets outside the encrypted
backend. Browser sessions should use
:class:`aeat.adapters.outbound.aeat.auth._certificate_backends._playwright_context.PlaywrightContextBackend`.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, override

from ......core.logging import get_logger
from ......core.time import now
from .._errors import AuthConfigurationError
from ._base import _CertBackend

if TYPE_CHECKING:
    from ..certificate import HandshakeResult, LoadedCertificate

log = get_logger(__name__)


class HttpxFallbackBackend(_CertBackend):
    """mTLS handshake probe that fails closed under the secure-storage policy.

    Verify-only backend; rejects any attempt to preload a browser
    context. See :class:`aeat.adapters.outbound.aeat.auth._certificate_backends.PlaywrightContextBackend`
    for the interactive counterpart.
    """

    @override
    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        """Reject the call — this backend cannot drive a browser context.

        Args:
            cert: Ignored.
            context: Ignored.

        Raises:
            AuthConfigurationError: Always.
        """
        raise AuthConfigurationError(
            "HTTPX_FALLBACK has no browser path; use PLAYWRIGHT_CONTEXT "
            "for interactive sessions. HTTPX_FALLBACK is verify-only.",
        )

    @override
    def verify(self, cert: LoadedCertificate, url: str) -> HandshakeResult:
        """Return a closed failure without materialising PEM/key files.

        :mod:`httpx` cannot consume in-memory PKCS#12 client certificates
        through Python's standard :mod:`ssl` API, and converting the
        certificate and private key to plaintext temporary files is
        forbidden because certificate secrets must not bypass the
        secure-storage boundary. The fallback therefore reports a closed
        failure rather than degrading the secrecy contract.

        Args:
            cert: The loaded PKCS#12 certificate to present.
            url: HTTPS endpoint to probe.

        Returns:
            A :class:`HandshakeResult` describing the closed-failure outcome.
        """
        from ..certificate import HandshakeResult

        attempted_at = now()
        started = time.perf_counter()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log.warning(
            "verify_handshake refused: backend=httpx_fallback url=%s elapsed_ms=%d thumbprint=%s",
            url,
            elapsed_ms,
            cert.sha256_thumbprint,
        )
        return HandshakeResult(
            success=False,
            status_code=0,
            server_cert_chain=(),
            elapsed_ms=elapsed_ms,
            attempted_at=attempted_at,
            error_message=(
                "HTTPX_FALLBACK is disabled because it requires plaintext PEM/key temp files; "
                "use PLAYWRIGHT_CONTEXT for AEAT client-certificate sessions."
            ),
        )
