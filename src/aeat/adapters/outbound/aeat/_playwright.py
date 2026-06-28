"""AEAT outbound Playwright exception aliases.

This module is import-safe without the optional ``browser`` extra: when
``playwright`` is absent the two exception aliases fall back to local stub
classes so every ``except PlaywrightError:`` site still imports and parses. A
missing extra can only mean the browser feature was never reached (no live
session can run without playwright), so a stub that never matches a real
playwright error is correct. The feature boundary itself guards on
``require_optional_extra(BROWSER_EXTRA)`` before launching playwright.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
except ImportError:  # the optional `browser` extra is not installed

    # TYPE-IGNORE-RATIONALE-OPTIONAL-BROWSER-EXTRA: fallback redefinition of the playwright
    # async_api name when the optional `browser` extra is absent (the real symbol is the import above).
    class PlaywrightError(Exception):  # type: ignore[no-redef]
        """Fallback for ``playwright.async_api.Error`` when the browser extra is absent."""

    # TYPE-IGNORE-RATIONALE-OPTIONAL-BROWSER-EXTRA: fallback redefinition when the optional
    # `browser` extra is absent (the real playwright.async_api.TimeoutError is the import above).
    class PlaywrightTimeoutError(PlaywrightError):  # type: ignore[no-redef]
        """Fallback for ``playwright.async_api.TimeoutError`` when the browser extra is absent."""


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
