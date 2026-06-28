"""Private certificate backend implementations.

This package is **private**. External callers MUST import from
:mod:`aeat.adapters.outbound.aeat.auth`; the backend dispatcher in
:mod:`aeat.adapters.outbound.aeat.auth.certificate` is the only legitimate
consumer. Backend implementations satisfy the abstract
:class:`~aeat.adapters.outbound.aeat.auth._certificate_backends._base._CertBackend`
contract for :class:`LoadedCertificate` context validation and
:class:`HandshakeResult` verification.

See Also:
    :mod:`aeat.adapters.outbound.aeat.auth.certificate`
        Public certificate model, loader, health, and backend-dispatch surface.
    :class:`~aeat.adapters.outbound.aeat.auth._certificate_backends._playwright_context.PlaywrightContextBackend`
        Primary backend for Playwright per-context client certificates.
    :class:`~aeat.adapters.outbound.aeat.auth._certificate_backends._httpx_fallback.HttpxFallbackBackend`
        Fail-closed verification backend that avoids plaintext PEM/key files.
"""
