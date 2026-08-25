"""Anti-bot evasion strategies for Playwright contexts.

:class:`adapters.outbound.aeat.browser.BrowserSession` applies an
:class:`EvasionStrategy` after creating each Playwright ``BrowserContext`` and
before returning it to auth providers or Sede readers. The default
:class:`PlaywrightStealthEvasion` delegates to the optional
``playwright-stealth`` package and raises :class:`BrowserEvasionError` with a
typed terminal outcome when that package is unavailable.

See Also:
    :meth:`adapters.outbound.aeat.browser.BrowserSession.create_context`
        Applies the configured evasion strategy during context preparation.
    :class:`adapters.outbound.aeat.browser.BrowserFailureMode`
        Carries ``EVASION_FAILED`` when strategy application fails inside the
        central session wrapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Never, Protocol

if TYPE_CHECKING:
    # playwright is the optional `browser` extra; this type is annotation-only.
    from playwright.async_api import BrowserContext

from .....core import NoRecoveryOutcome
from .....core.logging import get_logger
from ._errors import (
    BrowserEvasionError,
    BrowserFailureMode,
    BrowserPreconditionCondition,
    browser_no_action_verdict,
)

logger = get_logger(__name__)


def _raise_playwright_stealth_unavailable(cause: ImportError) -> Never:
    """Translate a missing stealth dependency into the browser safety contract."""
    raise BrowserEvasionError(
        "Browser evasion support is unavailable",
        failure_mode=BrowserFailureMode.EVASION_FAILED,
        precondition_verdict=browser_no_action_verdict(
            condition=BrowserPreconditionCondition.EVASION_SUPPORT_AVAILABLE,
            facts={"browser_evasion_support_available": False},
            outcome=NoRecoveryOutcome.SAFETY,
        ),
    ) from cause


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
        except ImportError as exc:
            logger.error("playwright-stealth is not installed; evasion failed", exc_info=True)
            _raise_playwright_stealth_unavailable(exc)

        await Stealth().apply_stealth_async(context)
        logger.debug("playwright-stealth evasion applied")
