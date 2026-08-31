"""Live AEAT authenticator verification — gated on env vars.

Asserts end-to-end that the operator's configured PKCS#12 bundle, when
fed through :class:`cadrumo.adapters.outbound.aeat.auth.AeatAuthenticator`,
produces a valid :class:`cadrumo.adapters.outbound.aeat.auth.AeatSession`
and that
:meth:`cadrumo.adapters.outbound.aeat.auth.AeatAuthenticator.verify`
returns ``is_valid=True`` only at the canonical protected resource.

After live opt-in, missing certificate configuration is a failing prerequisite.
"""

from __future__ import annotations

import pytest

from ......application.auth.protocols import BrowserSessionFactoryPort
from ......application.auth.session_types import AeatLoginAssertion, AeatSession
from ......application.auth_credentials import unnamed_certificate_credentials
from ......core.config import AEAT_CERTIFICATE_PROTECTED_URL, Settings
from ......tests.live_gate import requires_live_enabled
from ..authenticator import AeatAuthenticator
from ..certificate import CertificateHealthSeverity, extract_nif_from_subject

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def test_aeat_authenticator_synchronous_surface_live() -> None:
    """Exercise the sync authenticator surface against the real cert.

    This covers the paths that future remote-read modules call most
    often: ``health()`` and
    ``extract_nif_from_subject(load_certificate())``. It does NOT
    spin up Playwright; the async-context path is covered by the
    separate test below only when an injectable browser factory is
    available.
    """
    requires_live_enabled()
    settings = Settings()
    if settings.cadrumo_certificate_path is None or settings.cadrumo_certificate_password_secret is None:
        pytest.fail("AEAT certificate env vars are not fully configured after live opt-in")

    # Production cert loader reads the passphrase via
    # ``CertificateBundle.password`` (a SecretStr field on Settings);
    # the env-var round-trip is gone (see ``certificate.py`` docstring).
    # No os.environ bridge is needed.

    authenticator = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    )

    # Health severity must be OK or WARN — a CRITICAL/EXPIRED cert
    # means the operator should renew before running the live
    # pipeline, and surfaces as a test failure rather than a skip.
    health = authenticator.health()
    assert health.severity in {
        CertificateHealthSeverity.OK,
        CertificateHealthSeverity.WARN,
    }, f"cert health is {health.severity}; renew before live run"

    cert = authenticator.load_certificate()
    nif = extract_nif_from_subject(cert)
    assert nif, "could not extract NIF from FNMT certificate subject"
    # DNI: 7-8 digits + letter; NIE: X/Y/Z + 7 digits + letter.
    assert len(nif) in {8, 9}, f"unexpected NIF shape: {nif!r}"


@pytest.mark.asyncio
async def test_aeat_authenticator_full_live_flow() -> None:
    """End-to-end live authentication + login assertion.

    Requires Playwright to be installed and AEAT to be reachable.
    Uses the real ``BrowserSession`` factory via a thin adapter so
    no runtime substitution is involved.
    """
    requires_live_enabled()
    settings = Settings()
    if settings.cadrumo_certificate_path is None or settings.cadrumo_certificate_password_secret is None:
        pytest.fail("AEAT certificate env vars are not fully configured after live opt-in")

    from typing import Any, cast

    from ...browser import Profile
    from ...browser._factory import create_browser_session

    profile = Profile(name="live-auth-gate")

    async def factory(_settings: Any) -> Any:
        return await create_browser_session(settings, profile)

    typed_factory = cast(BrowserSessionFactoryPort, factory)
    async with AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=typed_factory,
    ) as auth:
        aeat_session = await auth.authenticate()
        assert isinstance(aeat_session, AeatSession)
        assert aeat_session.is_stale() is False
        assert aeat_session.identity_nif
        assertion = await auth.verify(aeat_session)
        assert isinstance(assertion, AeatLoginAssertion)
        assert assertion.is_valid is True, (
            f"login assertion invalid: status={assertion.status_code} err={assertion.error_message}"
        )
        assert assertion.target_url == AEAT_CERTIFICATE_PROTECTED_URL
        assert assertion.final_url == AEAT_CERTIFICATE_PROTECTED_URL
        assert assertion.response_successful is True
        assert assertion.parsed_nif == aeat_session.identity_nif
