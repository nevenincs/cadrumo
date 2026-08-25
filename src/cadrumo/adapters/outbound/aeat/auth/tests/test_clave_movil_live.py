"""Live Cl@ve Móvil Playwright auth probes.

These tests use the centralized AEAT browser backend against the real
AEAT Cl@ve Móvil surface. The entrypoint probe is non-interactive; the
provider probes use the real encrypted session store and only run when
the operator has opted in and configured the necessary Cl@ve state.
"""

from __future__ import annotations

import os
from urllib.parse import quote

import pytest

import cadrumo.adapters.outbound.aeat.auth.session_store as session_store

from ......core.config import Settings
from ......tests.live_gate import requires_live_enabled
from ...browser import default_browser_session_factory
from ..authenticator_types import AeatLoginAssertion, AeatSession
from ..clave_movil import ClaveMovilAuthProvider
from ..providers import ClaveMovilSessionDetail

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def _settings_or_skip() -> Settings:
    requires_live_enabled()
    return Settings()


async def _central_browser_session(settings: Settings):
    return await default_browser_session_factory(settings)


@pytest.mark.asyncio
async def test_clave_movil_playwright_entrypoint_reaches_live_selector() -> None:
    """Central Playwright backend reaches AEAT's live Cl@ve Móvil selector."""

    settings = _settings_or_skip()
    browser_session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
        page = await context.new_page()
        target_path = settings.aeat_sede_expedientes_path
        selector_url = settings.aeat_clave_sede_access_url_template.format(target=quote(target_path, safe=""))

        response = await browser_session.navigate(page, selector_url)
        assert response is None or 200 <= response.status < 500

        button = page.locator('button[name="autoriza-P"]').first
        await button.wait_for(state="visible", timeout=settings.cadrumo_clave_movil_timeout_ms)
        text = " ".join((await button.inner_text(timeout=settings.cadrumo_clave_movil_timeout_ms)).split())
        assert "Cl@ve" in text or "Móvil" in text
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


@pytest.mark.asyncio
async def test_clave_movil_provider_probes_persisted_session_with_central_playwright() -> None:
    """Real provider + central Playwright verify an existing encrypted Cl@ve session."""

    settings = _settings_or_skip()
    if not settings.cadrumo_clave_movil_dni_nie:
        pytest.fail("CADRUMO_CLAVE_MOVIL_DNI_NIE is not configured after live opt-in")
    from ......core.auth_session_keys import aeat_auth_session_storage_state_path
    from ......core.bucket_pointer import require_active_bucket_id

    storage_state_path = aeat_auth_session_storage_state_path(
        require_active_bucket_id(),
        "clave-movil-storage",
    )
    if not session_store.exists(storage_state_path):
        pytest.fail("No persisted encrypted Cl@ve Móvil session is available to probe after live opt-in")

    provider = ClaveMovilAuthProvider(settings, browser_session_factory=_central_browser_session)
    try:
        session, assertion = await provider.probe_persisted_session()
        assert isinstance(session, AeatSession)
        assert session.identity_nif == settings.cadrumo_clave_movil_dni_nie.get_secret_value().strip().upper()
        assert isinstance(session.provider_detail, ClaveMovilSessionDetail)
        assert isinstance(assertion, AeatLoginAssertion)
        assert assertion.is_valid is True, (
            f"persisted Cl@ve session probe failed: status={assertion.status_code} error={assertion.error_message}"
        )
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_clave_movil_provider_full_login_with_central_playwright_when_explicitly_enabled() -> None:
    """Run the real Cl@ve Móvil login flow through the centralized Playwright backend."""

    settings = _settings_or_skip()
    if os.environ.get("AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH") != "1":
        pytest.fail("AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH is not 1 after live opt-in")
    if not settings.cadrumo_clave_movil_dni_nie:
        pytest.fail("CADRUMO_CLAVE_MOVIL_DNI_NIE is not configured after live opt-in")

    provider = ClaveMovilAuthProvider(settings, browser_session_factory=_central_browser_session)
    try:
        session = await provider.authenticate()
        assert isinstance(session, AeatSession)
        assert session.identity_nif == settings.cadrumo_clave_movil_dni_nie.get_secret_value().strip().upper()
        assert isinstance(session.provider_detail, ClaveMovilSessionDetail)
        assertion = await provider.verify(session)
        assert assertion.is_valid is True, (
            f"fresh Cl@ve login assertion failed: status={assertion.status_code} error={assertion.error_message}"
        )
    finally:
        await provider.close()

    from ......core.auth_session_keys import aeat_auth_session_storage_state_path
    from ......core.bucket_pointer import require_active_bucket_id

    storage_state_path = aeat_auth_session_storage_state_path(
        require_active_bucket_id(),
        "clave-movil-storage",
    )
    assert session_store.exists(storage_state_path)
    assert not storage_state_path.exists()
    assert not storage_state_path.with_suffix(".meta.json").exists()

    probe_provider = ClaveMovilAuthProvider(settings, browser_session_factory=_central_browser_session)
    try:
        resumed_session, resumed_assertion = await probe_provider.probe_persisted_session()
        assert isinstance(resumed_session, AeatSession)
        assert resumed_session.identity_nif == settings.cadrumo_clave_movil_dni_nie.get_secret_value().strip().upper()
        assert isinstance(resumed_session.provider_detail, ClaveMovilSessionDetail)
        assert isinstance(resumed_assertion, AeatLoginAssertion)
        assert resumed_assertion.is_valid is True, (
            "persisted Cl@ve login assertion failed: "
            f"status={resumed_assertion.status_code} error={resumed_assertion.error_message}"
        )
    finally:
        await probe_provider.close()
