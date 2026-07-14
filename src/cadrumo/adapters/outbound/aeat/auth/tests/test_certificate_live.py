"""Live mTLS handshake smoke test for :mod:`cadrumo.adapters.outbound.aeat.auth.certificate`.

Drives :func:`cadrumo.adapters.outbound.aeat.auth.load_certificate` and
:func:`cadrumo.adapters.outbound.aeat.auth.verify_handshake` against the real AEAT
verify URL. Gated on ``CADRUMO_LIVE_TESTS_ENABLED=1`` and the certificate
environment variables being set on
:class:`cadrumo.core.config.Settings`; after live opt-in, missing certificate
configuration is a failing prerequisite.
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

    Deselected when ``CADRUMO_LIVE_TESTS_ENABLED`` is not ``"1"``; fails when the
    certificate path / password env vars are unset on
    :class:`cadrumo.core.config.Settings`.
    """
    requires_live_enabled()

    settings = Settings()
    if settings.cadrumo_certificate_path is None or settings.cadrumo_certificate_password_secret is None:
        pytest.fail("AEAT certificate env vars are not fully configured after live opt-in")

    bundle = CertificateBundle(
        path=settings.cadrumo_certificate_path,
        password=settings.cadrumo_certificate_password_secret,
        friendly_name=settings.cadrumo_certificate_friendly_name,
        backend=settings.cadrumo_certificate_backend,
    )
    loaded = load_certificate(bundle)
    result = verify_handshake(loaded, settings.aeat_certificate_verify_url)

    assert isinstance(result, HandshakeResult)
    assert result.success is True, f"handshake failed: {result.error_message}"
    assert 200 <= result.status_code < 500
