"""Live mTLS handshake smoke test for :mod:`aeat.adapters.outbound.aeat.auth.certificate`.

Drives :func:`aeat.adapters.outbound.aeat.auth.load_certificate` and
:func:`aeat.adapters.outbound.aeat.auth.verify_handshake` against the real AEAT
verify URL. Gated on ``AEAT_LIVE_TESTS_ENABLED=1`` and the certificate
environment variables being set on
:class:`aeat.core.config.Settings`; skips cleanly in every other
configuration so CI never fails when credentials are unavailable.
Contains zero test doubles.
"""

from __future__ import annotations

import pytest

from ......core.config import Settings
from ......tests.live_gate import requires_live_enabled
from .. import (
    CertificateBundle,
    HandshakeResult,
    load_certificate,
    verify_handshake,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def test_verify_handshake_live_against_aeat() -> None:
    """Load the operator's certificate and hit the configured AEAT verify URL.

    Skips when ``AEAT_LIVE_TESTS_ENABLED`` is not ``"1"`` or the
    certificate path / password env vars are unset on
    :class:`aeat.core.config.Settings`.
    """
    requires_live_enabled()

    settings = Settings()
    if settings.aeat_certificate_path is None or settings.aeat_certificate_password_secret is None:
        pytest.skip("AEAT certificate env vars are not fully configured")

    bundle = CertificateBundle(
        path=settings.aeat_certificate_path,
        password=settings.aeat_certificate_password_secret,
        friendly_name=settings.aeat_certificate_friendly_name,
        backend=settings.aeat_certificate_backend,
    )
    loaded = load_certificate(bundle)
    result = verify_handshake(loaded, settings.aeat_certificate_verify_url)

    assert isinstance(result, HandshakeResult)
    assert result.success is True, f"handshake failed: {result.error_message}"
    assert 200 <= result.status_code < 500
