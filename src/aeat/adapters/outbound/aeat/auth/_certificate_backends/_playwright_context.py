"""Playwright per-context client-certificate backend.

Playwright (Python, ``>=1.46``) exposes client certs as a per-context
kwarg on :meth:`playwright.async_api.Browser.new_context`::

    await browser.new_context(client_certificates=[{
        "origin": "https://sede.agenciatributaria.gob.es",
        "pfxPath": str(bundle.path),
        "passphrase": password_value,
    }])

There is **no post-hoc injection hook**: a context that was constructed
without ``client_certificates`` cannot be retrofitted with one. This
backend therefore validates the contract at call time rather than
mutating the context.

:class:`CertificateContextProvisioner` calls
:func:`build_client_certificates_kwarg` while creating a browser context and
then stamps :data:`CERTIFICATE_CONTEXT_MARKER`; :class:`PlaywrightContextBackend`
later checks that marker for the selected :class:`LoadedCertificate`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from ......core.logging import get_logger
from ......core.time import now
from ._base import CERTIFICATE_CONTEXT_MARKER, _CertBackend
from ._httpx_fallback import HttpxFallbackBackend

if TYPE_CHECKING:
    from ..certificate import HandshakeResult, LoadedCertificate

log = get_logger(__name__)


def build_client_certificates_kwarg(
    cert: LoadedCertificate,
    origin: str,
) -> list[dict[str, str]]:
    """Build the Playwright ``client_certificates`` kwarg for ``cert``.

    Materialises the passphrase from :class:`pydantic.SecretStr` at
    the exact call site and nowhere else. The returned list is wired
    directly into ``browser.new_context(client_certificates=...)`` by
    :mod:`aeat.adapters.outbound.aeat.browser`.

    Args:
        cert: The loaded PKCS#12 certificate.
        origin: URL origin to scope the cert to
            (e.g. ``"https://sede.agenciatributaria.gob.es"``).

    Returns:
        A single-element list of Playwright cert records.
    """
    # Secret materialised here; the caller must hand the list straight
    # to Playwright and discard it.
    password_value = cert._password.get_secret_value()
    return [
        {
            "origin": origin,
            "pfxPath": str(cert.source_path),
            "passphrase": password_value,
        },
    ]


class PlaywrightContextBackend(_CertBackend):
    """Primary backend — per-context client cert via Playwright.

    Implements the :class:`_CertBackend` contract for browser-driven
    certificate sessions. The ``preload`` leg validates the
    :data:`CERTIFICATE_CONTEXT_MARKER` stamp produced by
    :class:`CertificateContextProvisioner`. The ``verify`` leg delegates to
    :class:`HttpxFallbackBackend`, which fails closed unless a future backend
    can perform mTLS verification without materialising plaintext key files.
    """

    @override
    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        """Verify the context was constructed with this cert.

        The browser session layer is expected to tag the constructed
        :class:`playwright.async_api.BrowserContext` with an attribute
        named :data:`CERTIFICATE_CONTEXT_MARKER` matching ``cert.sha256_thumbprint``.
        If the marker is absent, raises
        :class:`aeat.adapters.outbound.aeat.auth.certificate.CertificateError`
        pointing the operator at :func:`build_client_certificates_kwarg`.

        Args:
            cert: The loaded PKCS#12 certificate.
            context: A Playwright :class:`~playwright.async_api.BrowserContext`
                object (typed as ``object`` to avoid leaking the
                Playwright dependency upward).

        Raises:
            CertificateError: When the context lacks the expected
                thumbprint marker.
        """
        from ..certificate import CertificateError

        marker = getattr(context, CERTIFICATE_CONTEXT_MARKER, None)
        if marker != cert.sha256_thumbprint:
            raise CertificateError(
                "BrowserContext was not constructed with the expected client "
                "certificate. Playwright requires client certs to be passed at "
                "browser.new_context() time via the client_certificates kwarg; "
                "use aeat.adapters.outbound.aeat.auth._certificate_backends._playwright_context."
                "build_client_certificates_kwarg() from the browser session "
                "factory and tag the resulting context with "
                f"{CERTIFICATE_CONTEXT_MARKER}={cert.sha256_thumbprint!r}.",
            )
        log.info(
            "verified playwright_context: thumbprint=%s",
            cert.sha256_thumbprint,
        )

    @override
    def verify(self, cert: LoadedCertificate, url: str) -> HandshakeResult:
        """Delegate to the fail-closed httpx fallback for handshake verification.

        The Playwright backend has no standalone handshake primitive —
        spinning up a full browser just to probe TLS would be wasteful. The
        fallback refuses verification rather than writing decrypted PEM/key
        material to temporary files.

        Args:
            cert: The loaded PKCS#12 certificate to present.
            url: HTTPS endpoint to probe.

        Returns:
            A :class:`HandshakeResult` describing the outcome.
        """
        _ = now()  # touch datetime so imports stay explicit
        return HttpxFallbackBackend().verify(cert, url)
