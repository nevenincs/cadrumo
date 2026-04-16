"""Playwright per-context client-certificate backend (primary).

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
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from aeat.auth._certificate_backends._base import _CertBackend
from aeat.auth._certificate_backends._httpx_fallback import HttpxFallbackBackend
from aeat.logging import get_logger

if TYPE_CHECKING:
    from aeat.auth.certificate import HandshakeResult, LoadedCertificate

log = get_logger(__name__)

_CONTEXT_CERTIFICATE_THUMBPRINTS: WeakKeyDictionary[object, str] = WeakKeyDictionary()


def build_client_certificates_kwarg(
    cert: LoadedCertificate,
    origin: str,
) -> list[dict[str, str]]:
    """Build the Playwright ``client_certificates`` kwarg for ``cert``.

    Materialises the passphrase from :class:`pydantic.SecretStr` at
    the exact call site and nowhere else. The returned list is wired
    directly into ``browser.new_context(client_certificates=...)`` by
    the browser session layer (see issue #8 follow-up in
    ``aeat.browser``).

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
        }
    ]


def mark_context_with_certificate(cert: LoadedCertificate, context: object) -> None:
    """Record cert provenance for ``context`` without mutating the object."""
    _CONTEXT_CERTIFICATE_THUMBPRINTS[context] = cert.sha256_thumbprint


class PlaywrightContextBackend(_CertBackend):
    """Primary backend — per-context client cert via Playwright."""

    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        """Verify the context was constructed with this cert.

        The browser session layer is expected to tag the constructed
        :class:`playwright.async_api.BrowserContext` in the sidecar
        registry managed by :func:`mark_context_with_certificate`
        using a thumbprint matching ``cert.sha256_thumbprint``. If the
        marker is absent, we raise
        :class:`CertificateError` pointing the operator at
        :func:`build_client_certificates_kwarg`.
        """
        from aeat.auth.certificate import CertificateError

        marker = _CONTEXT_CERTIFICATE_THUMBPRINTS.get(context)
        if marker != cert.sha256_thumbprint:
            raise CertificateError(
                "BrowserContext was not constructed with the expected client "
                "certificate. Playwright requires client certs to be passed at "
                "browser.new_context() time via the client_certificates kwarg; "
                "use aeat.auth._certificate_backends._playwright_context."
                "build_client_certificates_kwarg() from the browser session "
                "factory and register the resulting context via "
                "mark_context_with_certificate()."
            )
        log.info(
            "Verified PLAYWRIGHT_CONTEXT: thumbprint=%s friendly_name=%s",
            cert.sha256_thumbprint,
            cert.friendly_name,
        )

    def verify(self, cert: LoadedCertificate, url: str) -> HandshakeResult:
        """Delegate to the httpx fallback for the handshake smoke test.

        The Playwright backend has no standalone handshake primitive —
        spinning up a full browser just to probe TLS would be wasteful.
        We borrow :class:`HttpxFallbackBackend` for the verify leg.
        """
        _ = datetime.now(UTC)  # touch datetime so imports stay explicit
        return HttpxFallbackBackend().verify(cert, url)
