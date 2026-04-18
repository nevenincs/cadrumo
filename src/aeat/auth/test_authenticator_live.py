"""Live AEAT authenticator verification — gated on env vars.

This is the only live test introduced by issue #167. It asserts
end-to-end that the operator's configured PKCS#12 bundle, when
fed through :class:`AeatAuthenticator`, produces a valid
:class:`AeatSession` and that :meth:`AeatAuthenticator.verify_login`
returns ``is_valid=True`` against the configured verify URL.

The module carries zero mocks, patches, fakes, or monkey-patched
attributes — both the global `TID251` ruff ban and the extended
live-test banned-import set in ``tests/conftest.py`` forbid them.
The test skips cleanly when the cert env is not fully configured.
"""

from __future__ import annotations

import os

import pytest

from ..config import Settings
from . import (
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatSession,
    CertificateHealthSeverity,
    HandshakeResult,
)

pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]


def test_aeat_authenticator_synchronous_surface_live() -> None:
    """Exercise the sync authenticator surface against the real cert.

    This covers the paths that future remote-read modules call most
    often: ``health()``, ``verify_handshake()``,
    ``extract_nif_from_subject(load_certificate())``. It does NOT
    spin up Playwright; the async-context path is covered by the
    separate test below only when an injectable browser factory is
    available.
    """
    if os.environ.get("AEAT_LIVE_TESTS_ENABLED") != "1":
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not 1")
    settings = Settings()
    if settings.aeat_certificate_path is None or settings.aeat_certificate_password_secret is None:
        pytest.skip("AEAT certificate env vars are not fully configured")

    # Bridge the passphrase into the process environment for the
    # cert loader (same pattern as aeat.auth.test_certificate_live).
    os.environ.setdefault(
        "AEAT_CERTIFICATE_PASSWORD_SECRET",
        settings.aeat_certificate_password_secret.get_secret_value(),
    )

    authenticator = AeatAuthenticator(settings)

    # Health severity must be OK or WARN — a CRITICAL/EXPIRED cert
    # means the operator should renew before running the live
    # pipeline, and surfaces as a test failure rather than a skip.
    health = authenticator.health()
    assert health.severity in {
        CertificateHealthSeverity.OK,
        CertificateHealthSeverity.WARN,
    }, f"cert health is {health.severity}; renew before live run"

    handshake = authenticator.verify_handshake()
    assert isinstance(handshake, HandshakeResult)
    assert handshake.success is True, f"handshake failed: {handshake.error_message}"
    assert 200 <= handshake.status_code < 500

    cert = authenticator.load_certificate()
    nif = authenticator.extract_nif_from_subject(cert)
    assert nif, "could not extract NIF from FNMT certificate subject"
    # DNI: 7-8 digits + letter; NIE: X/Y/Z + 7 digits + letter.
    assert len(nif) in {8, 9}, f"unexpected NIF shape: {nif!r}"


@pytest.mark.asyncio
async def test_aeat_authenticator_full_live_flow() -> None:
    """End-to-end live authentication + login assertion.

    Requires Playwright to be installed and AEAT to be reachable.
    Uses the real ``BrowserSession`` factory via a thin adapter so
    zero monkey-patching is involved.
    """
    if os.environ.get("AEAT_LIVE_TESTS_ENABLED") != "1":
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not 1")
    settings = Settings()
    if settings.aeat_certificate_path is None or settings.aeat_certificate_password_secret is None:
        pytest.skip("AEAT certificate env vars are not fully configured")
    os.environ.setdefault(
        "AEAT_CERTIFICATE_PASSWORD_SECRET",
        settings.aeat_certificate_password_secret.get_secret_value(),
    )

    from typing import Any, cast

    from playwright.async_api import async_playwright

    from ..browser.profile import Profile
    from ..browser.session import BrowserSession
    from . import BrowserSessionFactory

    async with async_playwright() as playwright:
        profile = Profile(
            name="live-auth-gate",
            storage_state_path=settings.aeat_token_dir / "live_auth_gate_state.json",
        )
        session = BrowserSession(
            playwright=playwright,
            settings=settings,
            profile=profile,
        )

        async def factory(_settings: Any) -> Any:
            return session

        typed_factory = cast(BrowserSessionFactory, factory)
        async with AeatAuthenticator(settings, browser_session_factory=typed_factory) as auth:
            aeat_session = await auth.authenticate()
            assert isinstance(aeat_session, AeatSession)
            assert aeat_session.is_stale() is False
            assert aeat_session.identity_nif
            assertion = await auth.verify_login(aeat_session)
            assert isinstance(assertion, AeatLoginAssertion)
            assert assertion.is_valid is True, (
                f"login assertion invalid: status={assertion.status_code} err={assertion.error_message}"
            )
            assert assertion.identity_nif == aeat_session.identity_nif
