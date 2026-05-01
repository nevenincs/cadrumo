"""Live mTLS handshake smoke test for :mod:`aeat.auth.certificate`.

Gated on ``AEAT_LIVE_TESTS_ENABLED=1`` AND the cert env vars being set.
Skips cleanly in every other configuration — NEVER fails in CI when
credentials are unavailable. Contains zero mocks, fakes, or stubs.
"""

from __future__ import annotations

import os

import pytest

from .....core.config import Settings
from . import (
    CertificateBundle,
    HandshakeResult,
    load_certificate,
    verify_handshake,
)

pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]


def test_verify_handshake_live_against_aeat() -> None:
    """Load the operator's cert and hit the configured AEAT verify URL."""
    if os.environ.get("AEAT_LIVE_TESTS_ENABLED") != "1":
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not 1")

    settings = Settings()
    if settings.aeat_certificate_path is None or settings.aeat_certificate_password_secret is None:
        pytest.skip("AEAT certificate env vars are not fully configured")

    # The password env var name is the canonical one used by Settings.
    os.environ.setdefault(
        "AEAT_CERTIFICATE_PASSWORD_SECRET",
        settings.aeat_certificate_password_secret.get_secret_value(),
    )

    bundle = CertificateBundle(
        path=settings.aeat_certificate_path,
        password_env_var="AEAT_CERTIFICATE_PASSWORD_SECRET",
        friendly_name=settings.aeat_certificate_friendly_name,
        backend=settings.aeat_certificate_backend,
    )
    loaded = load_certificate(bundle)
    result = verify_handshake(loaded, settings.aeat_certificate_verify_url)

    assert isinstance(result, HandshakeResult)
    assert result.success is True, f"handshake failed: {result.error_message}"
    assert 200 <= result.status_code < 500
