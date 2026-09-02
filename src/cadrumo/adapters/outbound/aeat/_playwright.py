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
    :func:`adapters.outbound.aeat.browser.default_browser_session_factory`
        Production browser factory that reaches the guarded Playwright startup
        path.
    :class:`adapters.outbound.aeat.browser.BrowserError`
        Browser-layer envelope raised when the optional extra or Playwright
        startup fails.
    :func:`adapters.outbound.aeat.sede._browser_stage.run_playwright_stage`
        Sede stage wrapper that catches these aliases for timeout and transport
        mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright, Response
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import Locator as Locator
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
else:
    type BrowserContext = Any
    type Locator = Any
    type Page = Any
    type Playwright = Any
    type Response = Any
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    except ImportError:  # the optional `browser` extra is not installed

        class PlaywrightError(Exception):
            """Fallback for ``playwright.async_api.Error`` when the browser extra is absent.

            The fallback exists only so modules such as
            :mod:`adapters.outbound.aeat.browser` and
            :mod:`adapters.outbound.aeat.sede` can import their exception
            handlers before a live browser path is requested. It is not an AEAT
            registry-bound error; adapter boundaries catch and wrap it in registered
            Browser/Sede errors.
            """

            __bare_base_rationale__: ClassVar[str] = (
                "optional-extra fallback alias for playwright.async_api.Error; it must match the "
                "third-party exception shape when Playwright is absent and is only caught/wrapped by "
                "adapter boundaries"
            )

        class PlaywrightTimeoutError(PlaywrightError):
            """Fallback for ``playwright.async_api.TimeoutError`` without the browser extra.

            Sede stage helpers catch this alias alongside :class:`PlaywrightError`
            so timeout mapping remains importable even when Playwright is not
            installed.
            """


__all__ = [
    "BrowserContext",
    "Page",
    "Playwright",
    "PlaywrightError",
    "PlaywrightTimeoutError",
    "Response",
]
