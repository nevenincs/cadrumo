"""AEAT outbound Playwright exception aliases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

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
