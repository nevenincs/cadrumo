"""Live AEAT authenticator verification — gated on env vars.

Asserts end-to-end that the operator's configured PKCS#12 bundle, when
fed through :class:`aeat.adapters.outbound.aeat.auth.AeatAuthenticator`,
produces a valid :class:`aeat.adapters.outbound.aeat.auth.AeatSession`
and that
:meth:`aeat.adapters.outbound.aeat.auth.AeatAuthenticator.verify_login`
returns ``is_valid=True`` against the configured verify URL.

The test uses the configured certificate and live verification URL directly.
After live opt-in, missing certificate configuration is a failing prerequisite.
"""

from __future__ import annotations

import pytest

from ......core.config import Settings
from ......tests.live_gate import requires_live_enabled
from .. import (
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatSession,
    CertificateHealthSeverity,
    HandshakeResult,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def test_aeat_authenticator_synchronous_surface_live() -> None:
    """Exercise the sync authenticator surface against the real cert.

    This covers the paths that future remote-read modules call most
    often: ``health()``, ``verify_handshake()``,
    ``extract_nif_from_subject(load_certificate())``. It does NOT
    spin up Playwright; the async-context path is covered by the
    separate test below only when an injectable browser factory is
    available.
    """
    requires_live_enabled()
    settings = Settings()
    if settings.aeat_certificate_path is None or settings.aeat_certificate_password_secret is None:
        pytest.fail("AEAT certificate env vars are not fully configured after live opt-in")

    # Production cert loader reads the passphrase via
    # ``CertificateBundle.password`` (a SecretStr field on Settings);
    # the env-var round-trip is gone (see ``certificate.py`` docstring).
    # No os.environ bridge is needed.

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
    requires_live_enabled()
    settings = Settings()
    if settings.aeat_certificate_path is None or settings.aeat_certificate_password_secret is None:
        pytest.fail("AEAT certificate env vars are not fully configured after live opt-in")

    from typing import Any, cast

    from ...browser import Profile, create_browser_session
    from .. import BrowserSessionFactory

    profile = Profile(
        name="live-auth-gate",
        storage_state_path=settings.aeat_token_dir / "live_auth_gate_state.json",
    )

    async def factory(_settings: Any) -> Any:
        return await create_browser_session(settings, profile)

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
        assert assertion.parsed_nif == aeat_session.identity_nif
