"""Anti-bot evasion strategies for Playwright."""

from __future__ import annotations

from typing import Protocol

from playwright.async_api import BrowserContext

from aeat.logging import get_logger

logger = get_logger(__name__)


class EvasionStrategy(Protocol):
    """Protocol for applying evasion techniques to a BrowserContext."""

    async def apply(self, context: BrowserContext) -> None:
        """Apply anti-bot evasion techniques to the given context.

        Args:
            context: The Playwright BrowserContext to patch.
        """
        ...


class PlaywrightStealthEvasion:
    """Evasion strategy utilizing the playwright-stealth package."""

    async def apply(self, context: BrowserContext) -> None:
        """Apply playwright-stealth patches to the context.

        Args:
            context: The Playwright BrowserContext to patch.
        """
        try:
            import playwright_stealth

            await playwright_stealth.stealth_async(context)  # type: ignore
            logger.info("Successfully applied playwright-stealth evasion.")
        except ImportError as e:
            logger.error("playwright-stealth is not installed. Evasion failed.")
            raise RuntimeError("playwright-stealth is required for this evasion strategy.") from e
