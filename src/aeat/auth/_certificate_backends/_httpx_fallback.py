"""httpx-based mTLS handshake backend (verify-only).

Extracts PEM cert + key material from the in-memory PKCS#12, writes
them to securely-permissioned temp files, runs an HTTPS GET via
:mod:`httpx`, and unconditionally deletes the temp files in a
``try/finally`` block. The backend is limited to
:func:`verify_handshake` — it has no browser path.
"""

from __future__ import annotations

import contextlib
import os
import ssl
import stat
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from cryptography.hazmat.primitives import serialization

from aeat.auth._certificate_backends._base import _CertBackend
from aeat.logging import get_logger

if TYPE_CHECKING:
    from aeat.auth.certificate import HandshakeResult, LoadedCertificate

log = get_logger(__name__)


def _export_pem_material(cert: LoadedCertificate) -> tuple[bytes, bytes]:
    """Return ``(cert_pem, key_pem)`` bytes from ``cert``'s private key + x509.

    Re-parses ``_pkcs12_bytes`` with the in-memory passphrase so we
    never hand the raw PFX to httpx (which does not accept it) and
    never write it unencrypted to disk.
    """
    from cryptography.hazmat.primitives.serialization import pkcs12

    password_bytes = cert._password.get_secret_value().encode("utf-8")
    parsed = pkcs12.load_pkcs12(cert._pkcs12_bytes, password_bytes)
    if parsed.key is None or parsed.cert is None or parsed.cert.certificate is None:
        raise ValueError("PKCS#12 bundle missing key or certificate")

    cert_pem = parsed.cert.certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = parsed.key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def _write_secure_tempfile(suffix: str, payload: bytes) -> Path:
    """Write ``payload`` to a 0600-permissioned temp file and return its Path."""
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    path = Path(tmp_path)
    # Windows semantics differ; best-effort 0600 on POSIX.
    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return path


class HttpxFallbackBackend(_CertBackend):
    """mTLS handshake probe via :mod:`httpx`."""

    def preload(
        self,
        cert: LoadedCertificate,
        context: object,
    ) -> None:
        """HTTPX_FALLBACK has no browser path.

        Raises:
            NotImplementedError: Always. This backend can only verify
                handshakes, never drive a Playwright context.
        """
        raise NotImplementedError(
            "HTTPX_FALLBACK has no browser path; use PLAYWRIGHT_CONTEXT "
            "for interactive sessions. HTTPX_FALLBACK is verify-only."
        )

    def verify(self, cert: LoadedCertificate, url: str) -> HandshakeResult:
        """Perform a real mTLS GET against ``url``.

        TLS and network errors are captured and returned as
        :class:`HandshakeResult` with ``success=False``. The method
        never logs the passphrase or any PEM byte.
        """
        from aeat.auth.certificate import HandshakeResult

        attempted_at = datetime.now(UTC)
        started = time.perf_counter()
        cert_path: Path | None = None
        key_path: Path | None = None

        try:
            cert_pem, key_pem = _export_pem_material(cert)
            cert_path = _write_secure_tempfile(".pem", cert_pem)
            key_path = _write_secure_tempfile(".key", key_pem)

            ssl_ctx = ssl.create_default_context()
            ssl_ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

            with httpx.Client(verify=ssl_ctx, timeout=20.0, follow_redirects=False) as client:
                response = client.get(url)

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            log.info(
                "verify_handshake OK: url=%s status=%d elapsed_ms=%d thumbprint=%s",
                url,
                response.status_code,
                elapsed_ms,
                cert.sha256_thumbprint,
            )
            return HandshakeResult(
                success=True,
                status_code=response.status_code,
                server_cert_chain=(),
                elapsed_ms=elapsed_ms,
                attempted_at=attempted_at,
                error_message=None,
            )
        except (httpx.HTTPError, ssl.SSLError, OSError, ValueError) as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            log.warning(
                "verify_handshake FAILED: url=%s elapsed_ms=%d error=%s",
                url,
                elapsed_ms,
                exc,
            )
            return HandshakeResult(
                success=False,
                status_code=0,
                server_cert_chain=(),
                elapsed_ms=elapsed_ms,
                attempted_at=attempted_at,
                error_message=f"{type(exc).__name__}: {exc}",
            )
        finally:
            for path in (cert_path, key_path):
                if path is not None:
                    with contextlib.suppress(OSError):
                        path.unlink(missing_ok=True)
