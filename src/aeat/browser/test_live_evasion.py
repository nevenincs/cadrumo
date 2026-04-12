"""Live tests for bot evasion strategies."""

import os

import pytest
from playwright.async_api import async_playwright

from aeat.browser.profile import Profile
from aeat.browser.session import BrowserSession
from aeat.config import load_settings


@pytest.mark.asyncio
@pytest.mark.live
async def test_live_bot_detection_probe(tmp_path) -> None:
    """Test the browser session against a live bot detection probe.

    Requires AEAT_LIVE_TESTS_ENABLED=true or AEAT_LIVE_TESTS=1.
    """
    if os.environ.get("AEAT_LIVE_TESTS") != "1" and os.environ.get("AEAT_LIVE_TESTS_ENABLED", "").lower() not in (
        "true",
        "1",
    ):
        pytest.skip("Live tests disabled")

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
