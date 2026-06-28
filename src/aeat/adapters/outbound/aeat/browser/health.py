"""Smoke-check entry point for the Playwright browser setup.

The health check constructs the production
:func:`default_browser_session_factory`, opens a browser context, and navigates
through :meth:`aeat.adapters.outbound.aeat.browser.BrowserSession.navigate`.
It verifies the local Playwright/browser installation path rather than the AEAT
site-health parser corpus; parser classifications are represented separately by
:class:`aeat.adapters.outbound.aeat.browser.SiteHealthStatus`.
"""

from __future__ import annotations

import asyncio

from .....core.config import load_settings
from .....core.logging import get_logger
from .._playwright import PlaywrightError
from ._factory import default_browser_session_factory
from .session import BrowserError

logger = get_logger(__name__)


async def run_health_check() -> None:
    """Run a smoke test to verify Playwright installation and evasion patches.

    The check uses :func:`default_browser_session_factory` so failures exercise
    the same optional ``browser`` extra, :class:`BrowserError` wrapping, evasion,
    context creation, and navigation path used by production auth and Sede
    readers.

    Raises:
        BrowserError: If the health check fails.
    """
    settings = load_settings()
    logger.info("browser health check starting")

    try:
        browser_session = await default_browser_session_factory(settings)
        try:
            context = await browser_session.create_context()
            page = await context.new_page()

            logger.debug("navigating to https://example.com for smoke test")
            response = await browser_session.navigate(page, "https://example.com")

            if not response or not response.ok:
                raise BrowserError(f"Smoke test failed. Status: {response.status if response else 'Unknown'}")

            logger.info("browser health check passed title=%s", await page.title())
            await context.close()
        finally:
            await browser_session.close()
    except BrowserError:
        raise
    except PlaywrightError as e:
        logger.error("browser health check failed", exc_info=True)
        raise BrowserError(f"BrowserHealthCheck failed: {e}") from e


def main() -> None:
    """Run :func:`run_health_check` from synchronous callers."""
    asyncio.run(run_health_check())


if __name__ == "__main__":
    main()
