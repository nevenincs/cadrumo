"""Typed navigation-timeout outcome for the declaraciones register drive.

``capture_expedientes`` (the ``aeat app live expedientes pull`` verb) reaches
AEAT through ``DeclaracionesRegisterSession.walk`` -> ``_drive_search``, the same
form-drive helper :mod:`test_declarations_live` exercises against the real
sede. This suite drives the real ``_drive_search`` coroutine through a local
headless Chromium page whose intercepted navigation is deliberately stalled.
It proves the production code maps a real Playwright navigation timeout to a
typed, failure-mode-tagged :exc:`SedeNavigationError` without contacting AEAT.
"""

from __future__ import annotations

import asyncio

import pytest
from playwright.async_api import Route, async_playwright

from ......core.config import override_settings
from ..._playwright import PlaywrightTimeoutError
from .._declarations import _drive_search
from ..errors import SedeFailureMode, SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


async def _stall_navigation(route: Route) -> None:
    """Keep a real browser route pending beyond the configured deadline."""
    await asyncio.sleep(0.5)
    await route.abort()


@pytest.mark.asyncio
async def test_navigation_timeout_raises_typed_navigation_error() -> None:
    """A goto timeout surfaces as a typed, non-leaking navigation failure."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.route("**/*", _stall_navigation)
            with (
                override_settings(cadrumo_browser_navigation_timeout_ms=50),
                pytest.raises(SedeNavigationError) as exc_info,
            ):
                await _drive_search(page, modelo="100", ejercicio=2022)
        finally:
            await browser.close()

    assert exc_info.value.failure_mode == SedeFailureMode.LIVE_NAVIGATION_FAILED
    assert exc_info.value.context is not None
    assert exc_info.value.context["stage"] == "listing_goto"
    assert exc_info.value.context["modelo"] == "100"
    assert exc_info.value.context["ejercicio"] == 2022
    # The raw Playwright exception is chained, never swallowed silently.
    assert isinstance(exc_info.value.__cause__, PlaywrightTimeoutError)
