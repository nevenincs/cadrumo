"""Deferred backend: install cert into OS store + launch with user-data-dir.

This backend is intentionally stubbed. It would install the PKCS#12 into
the host OS cert store (macOS Keychain, Windows ``CertUtil -importpfx``,
Linux NSS DB) and launch Chrome with ``--user-data-dir`` so the browser
presents the cert automatically. The cross-OS install matrix and
teardown discipline are significant enough that the decision has been
deferred — see ``.vault/adr/2026-04-12-cert-auth-adr.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aeat.auth._certificate_backends._base import _CertBackend

if TYPE_CHECKING:
    from aeat.auth.certificate import HandshakeResult, LoadedCertificate


class UserDataDirBackend(_CertBackend):
    """Stub implementation — every method raises :class:`NotImplementedError`."""

    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        raise NotImplementedError(
            "USER_DATA_DIR backend is deferred; see .vault/adr/2026-04-12-cert-auth-adr.md for rationale."
        )

    def verify(self, cert: LoadedCertificate, url: str) -> HandshakeResult:
        raise NotImplementedError("USER_DATA_DIR backend is deferred; use HTTPX_FALLBACK for verify.")
