"""Live tests for bot evasion strategies."""

import pytest
from playwright.async_api import async_playwright

from ..cli._live import requires_live_enabled
from ..config import load_settings
from .profile import Profile
from .session import BrowserSession

pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]


@pytest.mark.asyncio
async def test_live_bot_detection_probe(tmp_path) -> None:
    """Test the browser session against a live bot detection probe.

    Gated by the ``live_read`` module-level marker (excluded from the default
    ``just test`` selection) and by ``AEAT_LIVE_TESTS_ENABLED`` when invoked
    via ``just test-live``.
    """
    requires_live_enabled()

    settings = load_settings()
    profile = Profile(name="live_test", storage_state_path=tmp_path / "live_state.json")

    async with async_playwright() as p:
        session = BrowserSession(playwright=p, settings=settings, profile=profile)
        context = await session.create_context()
        page = await context.new_page()

        response = await page.goto("https://bot.sannysoft.com/", wait_until="networkidle")
        assert response is not None
        assert response.ok

        webdriver_result = await page.evaluate("navigator.webdriver")
        assert webdriver_result is False, "navigator.webdriver is True, bot detected!"

        await context.close()
