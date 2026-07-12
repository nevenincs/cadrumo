"""Private certificate backend implementations.

This package is **private**. External callers MUST import from
:mod:`adapters.outbound.aeat.auth`; the backend dispatcher in
:mod:`adapters.outbound.aeat.auth.certificate` is the only legitimate
consumer. Backend implementations satisfy the abstract
:class:`adapters.outbound.aeat.auth._certificate_backends._base._CertBackend`
contract for :class:`adapters.outbound.aeat.auth.LoadedCertificate` context
validation and :class:`adapters.outbound.aeat.auth.HandshakeResult`
verification.

See Also:
    :mod:`adapters.outbound.aeat.auth.certificate`
        Public certificate model, loader, health, and backend-dispatch surface.
    :class:`adapters.outbound.aeat.auth._certificate_backends._playwright_context.PlaywrightContextBackend`
        Primary backend for Playwright per-context client certificates.
    :class:`adapters.outbound.aeat.auth._certificate_backends._httpx_fallback.HttpxFallbackBackend`
        Fail-closed verification backend that avoids plaintext PEM/key files.
"""
