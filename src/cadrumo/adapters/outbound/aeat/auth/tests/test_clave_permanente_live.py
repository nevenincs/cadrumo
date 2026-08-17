"""Live Cl@ve Permanente Playwright auth probes.

These tests use the centralized AEAT browser backend against the real
AEAT Cl@ve Permanente surface. Routine Cl@ve Permanente login for AEAT read
paths is headless-automatable (DNI/NIE + password, no SMS), so — unlike the
human-in-the-loop Cl@ve Móvil live probes — a single opt-in flag gates both
the selector-reachability probe and the full login flow; there is no
separate "explicitly enabled full login" escalation because no operator
interaction is required. Everything here stays dry-run by default per
``CADRUMO_LIVE_TESTS_ENABLED``; the tool never submits, only authenticates for
subsequent reads.

See Also:
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteAuthProvider`
        Live provider exercised for fresh login, verify, encrypted persistence,
        and resume.
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteSessionDetail`
        Provider-specific session payload asserted after live authentication.
    :func:`~adapters.outbound.aeat.browser.default_browser_session_factory`
        Central Playwright backend used by the live probe.
    :class:`~adapters.outbound.aeat.browser.BrowserSession`
        Browser runtime whose context construction owns storage-state injection.
    :mod:`~adapters.outbound.aeat.auth.tests.test_clave_permanente`
        Protocol-level companion suite covering deterministic provider branches.
"""

from __future__ import annotations

from urllib.parse import quote

import pytest

from ......core.config import Settings
from ......tests.live_gate import requires_live_enabled
from ...browser import default_browser_session_factory
from .. import (
    AeatLoginAssertion,
    AeatSession,
    ClavePermanenteAuthProvider,
    ClavePermanenteSessionDetail,
    _session_store,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def _settings_or_skip() -> Settings:
    requires_live_enabled()
    return Settings()


async def _central_browser_session(settings: Settings):
    return await default_browser_session_factory(settings)


@pytest.mark.asyncio
async def test_clave_permanente_playwright_entrypoint_reaches_live_selector() -> None:
    """Central Playwright backend reaches AEAT's live Cl@ve Permanente selector."""
    settings = _settings_or_skip()
    browser_session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
        page = await context.new_page()
        target_path = settings.aeat_sede_expedientes_path
        selector_url = settings.aeat_clave_permanente_sede_access_url_template.format(
            target=quote(target_path, safe=""),
        )

        response = await browser_session.navigate(page, selector_url)
        assert response is None or 200 <= response.status < 500
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


@pytest.mark.asyncio
async def test_clave_permanente_provider_full_login_with_central_playwright() -> None:
    """Run the real Cl@ve Permanente login flow through the centralized Playwright backend.

    Routine Cl@ve Permanente login for AEAT read paths requires no
    operator interaction, so this test opts in on the shared live-test
    flag alone (``CADRUMO_LIVE_TESTS_ENABLED``) plus configured credentials —
    no additional escalation flag, unlike the human-in-the-loop Cl@ve
    Móvil live suite.
    """
    settings = _settings_or_skip()
    if not settings.cadrumo_clave_permanente_dni_nie or not settings.cadrumo_clave_permanente_password:
        pytest.fail(
            "CADRUMO_CLAVE_PERMANENTE_DNI_NIE and CADRUMO_CLAVE_PERMANENTE_PASSWORD "
            "are not both configured after live opt-in",
        )

    provider = ClavePermanenteAuthProvider(settings, browser_session_factory=_central_browser_session)
    try:
        session = await provider.authenticate()
        assert isinstance(session, AeatSession)
        expected_identity = settings.cadrumo_clave_permanente_dni_nie.get_secret_value().strip().upper()
        assert session.identity_nif == expected_identity
        assert isinstance(session.provider_detail, ClavePermanenteSessionDetail)
        assertion = await provider.verify(session)
        assert assertion.is_valid is True, (
            f"fresh Cl@ve Permanente login assertion failed: "
            f"status={assertion.status_code} error={assertion.error_message}"
        )
    finally:
        await provider.close()

    from ......core import require_active_bucket_id
    from ......core.auth_session_keys import aeat_auth_session_storage_state_path

    storage_state_path = aeat_auth_session_storage_state_path(
        require_active_bucket_id(),
        "clave-permanente-storage",
    )
    assert _session_store.exists(storage_state_path)
    assert not storage_state_path.exists()
    assert not storage_state_path.with_suffix(".meta.json").exists()

    resume_provider = ClavePermanenteAuthProvider(settings, browser_session_factory=_central_browser_session)
    try:
        resumed_session = await resume_provider.authenticate()
        assert isinstance(resumed_session, AeatSession)
        assert resumed_session.identity_nif == expected_identity
        assert isinstance(resumed_session.provider_detail, ClavePermanenteSessionDetail)
        resumed_assertion = await resume_provider.verify(resumed_session)
        assert isinstance(resumed_assertion, AeatLoginAssertion)
        assert resumed_assertion.is_valid is True, (
            "persisted Cl@ve Permanente login assertion failed: "
            f"status={resumed_assertion.status_code} error={resumed_assertion.error_message}"
        )
    finally:
        await resume_provider.close()
