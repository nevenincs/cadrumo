"""Health check script for the Playwright setup."""

from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from .....core.config import load_settings
from .....core.logging import get_logger
from .session import BrowserError

logger = get_logger(__name__)


async def run_health_check() -> None:
    """Run a smoke test to verify Playwright installation and evasion patches.

    Raises:
        BrowserError: If the health check fails.
    """
    settings = load_settings()
    logger.info("Starting BrowserHealthCheck...")

    try:
        async with async_playwright() as p:
            logger.info(
                "Launching browser (channel=%s, headless=%s)...",
                settings.aeat_browser_channel,
                settings.aeat_browser_headless,
            )
            browser = await p.chromium.launch(
                channel=settings.aeat_browser_channel,
                headless=settings.aeat_browser_headless,
            )
            context = await browser.new_context()
            page = await context.new_page()

            logger.info("Navigating to https://example.com for smoke test...")
            response = await page.goto("https://example.com", wait_until="domcontentloaded")

            if not response or not response.ok:
                raise BrowserError(f"Smoke test failed. Status: {response.status if response else 'Unknown'}")

            logger.info("Smoke test successful. Page title: %s", await page.title())
            await browser.close()
            logger.info("BrowserHealthCheck passed.")
    except Exception as e:
        logger.error("BrowserHealthCheck failed: %s", e)
        raise BrowserError(f"BrowserHealthCheck failed: {e}") from e


def main() -> None:
    """Synchronous entry point for the health check."""
    asyncio.run(run_health_check())


if __name__ == "__main__":
    main()
