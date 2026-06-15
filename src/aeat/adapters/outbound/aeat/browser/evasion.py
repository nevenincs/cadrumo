"""Anti-bot evasion strategies for Playwright."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    # playwright is the optional `browser` extra; this type is annotation-only.
    from playwright.async_api import BrowserContext

from .....core.logging import get_logger
from ._errors import BrowserEvasionError

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
    """Evasion strategy utilizing the playwright-stealth package.

    Targets the ``playwright-stealth`` 2.x class-based API
    (``Stealth().apply_stealth_async``). The 1.x module-level
    ``stealth_async`` helper was removed upstream.
    """

    async def apply(self, context: BrowserContext) -> None:
        """Apply playwright-stealth patches to the context.

        Args:
            context: The Playwright BrowserContext to patch.

        Raises:
            BrowserEvasionError: If the ``playwright-stealth`` package is not installed.
        """
        try:
            from playwright_stealth import Stealth
        except ImportError as e:
            from .....core import BROWSER_EXTRA

            logger.error("playwright-stealth is not installed; evasion failed", exc_info=True)
            raise BrowserEvasionError(
                "playwright-stealth is required for this evasion strategy.",
                suggestion=BROWSER_EXTRA.install_hint,
            ) from e

        await Stealth().apply_stealth_async(context)
        logger.debug("playwright-stealth evasion applied")
