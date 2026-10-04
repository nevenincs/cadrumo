"""A delayed AEAT alert cannot strand an authenticated own-name continuation."""

from pathlib import Path
from typing import cast, override

import pytest
from playwright.async_api import Page

from ......application.auth.protocols import BrowserPagePort
from ......core.config import Settings
from ...browser.tests.real_http_boundary import open_real_browser_session, opened_http_boundary
from ..clave_movil import ClaveMovilAuthProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter, pytest.mark.usefixtures("operation")]


class _LateAlertProvider(ClaveMovilAuthProvider):
    """Insert the overlay after the first inspection, before the actual browser click."""

    inspections = 0

    @override
    async def _dismiss_pre303_alert_modal_if_present(self, page: BrowserPagePort) -> bool:
        dismissed = await super()._dismiss_pre303_alert_modal_if_present(page)
        self.inspections += 1
        if self.inspections == 1:
            await cast("Page", page).evaluate("document.querySelector('#alertsModal').style.display = 'block'")
        return dismissed


@pytest.mark.asyncio
async def test_alert_appearing_after_inspection_is_dismissed_before_retry(tmp_path: Path) -> None:
    """Real browser hit testing blocks the first click; the bounded recovery reaches confirmation."""
    settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_browser_navigation_timeout_ms=500)
    async with opened_http_boundary() as boundary:
        playwright, session = await open_real_browser_session(
            boundary=boundary, settings=settings, profile_name="late-representation-alert"
        )
        try:
            context = await session.create_context()
            page = await context.new_page()
            await page.set_content("""
                <form id="repForm"><input id="propio" name="representacion" type="radio" checked>
                <label for="propio">Actuar en nombre propio</label>
                <input id="representante" name="representacion" type="radio"></form>
                <button type="submit" onclick="document.body.dataset.confirmed='yes'">Confirmar</button>
                <div id="alertsModal" class="modal" style="display:none;position:fixed;inset:0;z-index:100;background:white">
                    <button type="button" onclick="this.parentElement.style.display='none'">Continuar</button>
                </div>
            """)
            provider = _LateAlertProvider(settings)
            await provider._continue_own_name_representation(page)
            assert await page.get_attribute("body", "data-confirmed") == "yes"
            assert provider.inspections == 2
        finally:
            await session.close()
            await playwright.stop()
