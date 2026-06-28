"""Import-safe Playwright aliases for AEAT outbound adapters.

Browser and Sede modules import ``PlaywrightError`` and
``PlaywrightTimeoutError`` to classify navigation, context, and stage
failures. This module remains import-safe without the optional ``browser``
extra: when ``playwright`` is absent, the aliases fall back to local exception
classes so ``except PlaywrightError`` sites still import and parse.

A missing extra can only mean the live browser feature was never reached. The
actual launch boundary still guards through the project ``browser`` extra before
starting Playwright, so the fallback classes are placeholders for importability,
not a second execution path.

See Also:
    :func:`aeat.adapters.outbound.aeat.browser.default_browser_session_factory`
        Production browser factory that reaches the guarded Playwright startup
        path.
    :class:`aeat.adapters.outbound.aeat.browser.BrowserError`
        Browser-layer envelope raised when the optional extra or Playwright
        startup fails.
    :func:`aeat.adapters.outbound.aeat.sede._browser_stage.run_playwright_stage`
        Sede stage wrapper that catches these aliases for timeout and transport
        mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ....core.errors import CoreError

try:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
except ImportError:  # the optional `browser` extra is not installed

    # TYPE-IGNORE-RATIONALE-OPTIONAL-BROWSER-EXTRA: fallback redefinition of the playwright
    # async_api name when the optional `browser` extra is absent (the real symbol is the import above).
    class PlaywrightError(CoreError):  # type: ignore[no-redef]
        """Fallback for ``playwright.async_api.Error`` when the browser extra is absent.

        The fallback exists only so modules such as
        :mod:`aeat.adapters.outbound.aeat.browser` and
        :mod:`aeat.adapters.outbound.aeat.sede` can import their exception
        handlers before a live browser path is requested.
        """

    # TYPE-IGNORE-RATIONALE-OPTIONAL-BROWSER-EXTRA: fallback redefinition when the optional
    # `browser` extra is absent (the real playwright.async_api.TimeoutError is the import above).
    class PlaywrightTimeoutError(PlaywrightError):  # type: ignore[no-redef]
        """Fallback for ``playwright.async_api.TimeoutError`` without the browser extra.

        Sede stage helpers catch this alias alongside :class:`PlaywrightError`
        so timeout mapping remains importable even when Playwright is not
        installed.
        """


if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright, Response
else:
    type BrowserContext = Any
    type Page = Any
    type Playwright = Any
    type Response = Any

__all__ = [
    "BrowserContext",
    "Page",
    "Playwright",
    "PlaywrightError",
    "PlaywrightTimeoutError",
    "Response",
]
