"""Deferred backend: local mTLS-injecting proxy.

This backend is intentionally stubbed. It would run a local proxy
(e.g. mitmproxy, Envoy) that terminates the browser's HTTPS leg and
re-establishes an outbound mTLS session using the PKCS#12 bundle. The
operational complexity of running + trusting such a proxy outweighs
the benefit for the primary use case today — see
``.vault/adr/2026-04-12-cert-auth-adr.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._base import _CertBackend

if TYPE_CHECKING:
    from ..certificate import HandshakeResult, LoadedCertificate


class MtlsProxyBackend(_CertBackend):
    """Stub implementation — every method raises :class:`NotImplementedError`."""

    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        raise NotImplementedError(
            "MTLS_PROXY backend is deferred; see .vault/adr/2026-04-12-cert-auth-adr.md for rationale."
        )

    def verify(self, cert: LoadedCertificate, url: str) -> HandshakeResult:
        raise NotImplementedError("MTLS_PROXY backend is deferred; use HTTPX_FALLBACK for verify.")
