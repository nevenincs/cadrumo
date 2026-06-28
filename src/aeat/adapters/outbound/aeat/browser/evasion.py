"""Anti-bot evasion strategies for Playwright contexts.

:class:`aeat.adapters.outbound.aeat.browser.BrowserSession` applies an
:class:`EvasionStrategy` after creating each Playwright ``BrowserContext`` and
before returning it to auth providers or Sede readers. The default
:class:`PlaywrightStealthEvasion` delegates to the optional
``playwright-stealth`` package and raises :class:`BrowserEvasionError` with the
browser-extra install hint when that package is unavailable.

See Also:
    :meth:`aeat.adapters.outbound.aeat.browser.BrowserSession.create_context`
        Applies the configured evasion strategy during context preparation.
    :class:`aeat.adapters.outbound.aeat.browser.BrowserFailureMode`
        Carries ``EVASION_FAILED`` when strategy application fails inside the
        central session wrapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    # playwright is the optional `browser` extra; this type is annotation-only.
    from playwright.async_api import BrowserContext

from .....core.logging import get_logger
from ._errors import BrowserEvasionError

logger = get_logger(__name__)


class EvasionStrategy(Protocol):
    """Protocol for applying evasion techniques to a Playwright context.

    Custom implementations can be supplied to :class:`BrowserSession` tests or
    adapter callers; production code defaults to :class:`PlaywrightStealthEvasion`.
    """

    async def apply(self, context: BrowserContext) -> None:
        """Apply anti-bot evasion techniques to the given context.

        Args:
            context: The Playwright BrowserContext to patch.
        """
        ...


class PlaywrightStealthEvasion:
    """Evasion strategy backed by the ``playwright-stealth`` package.

    Targets the ``playwright-stealth`` 2.x class-based API
    (``Stealth().apply_stealth_async``). The 1.x module-level
    ``stealth_async`` helper was removed upstream.
    """

    async def apply(self, context: BrowserContext) -> None:
        """Apply ``playwright-stealth`` patches to ``context``.

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
