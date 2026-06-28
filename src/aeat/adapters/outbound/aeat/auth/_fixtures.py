"""Shared test constants for the AEAT outbound auth package.

The certificate and authenticator tests use these constants to build real
PKCS#12 bundles with one canonical passphrase. Test code wraps
``SECRET_PASSPHRASE`` in :class:`pydantic.SecretStr` before constructing
:class:`CertificateBundle`, then reuses the same value when helper fixtures load
:class:`LoadedCertificate` records or exercise :class:`AeatAuthenticator`.

Module name intentionally does NOT start with ``_test_`` so the
:mod:`aeat.tests.test_marker_integrity` glob (``**/_test_*.py``) does
not pick it up as a test module — this file holds shared constants,
not tests, and carries no ``pytestmark``.

See Also:
    :mod:`aeat.adapters.outbound.aeat.auth.certificate`
        Production certificate models and loading helpers exercised by the
        certificate tests.
"""

from __future__ import annotations

# Canonical PKCS#12 passphrase for real self-signed bundle generation in tests.
SECRET_PASSPHRASE = "correct-horse-battery-staple"
