"""One headless launch of an installed Chromium build, for the browser's full check.

The launch names the revision-exact executable directly, so it proves that
file starts rather than whichever build Playwright would otherwise resolve. It
opens no page and reaches no network: it starts the browser, reads the version
the browser reports and closes it. A launch that fails names its cause in
closed words; the driver's and the browser's own messages are never kept.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ....application.provisioning_browser import BrowserLaunchFailureCause, BrowserLaunchReading
from ....core.diagnostic_log import DiagnosticValue, diagnostic_error_fields, diagnostic_event
from ....core.logging import get_logger
from ....core.optional_extras import BROWSER_EXTRA, MissingOptionalExtraError, require_optional_extra

__all__ = ["launch_headless_browser"]

_log = get_logger(__name__)

_UNRUNNABLE_WORDS = ("enoent", "eacces", "spawn")
_EXITED_WORDS = ("has been closed", "target closed", "browser closed", "process did exit", "exitcode")
_TIMEOUT_WORDS = ("timeout",)


def _failed(
    category: DependencyFailureCategory, cause: BrowserLaunchFailureCause, error: BaseException | None = None
) -> BrowserLaunchReading:
    """Return the failed reading and log its closed cause with the error's type and origin, never its message."""
    fields: dict[str, DiagnosticValue] = {"cause": cause.value, "failure_category": category.value}
    if error is not None:
        fields |= diagnostic_error_fields(error)
    diagnostic_event(_log, "browser_launch_failed", fields=fields, level=logging.WARNING)
    return BrowserLaunchReading(failure_category=category, failure_cause=cause)


def _driver_failure(error: BaseException) -> BrowserLaunchReading:
    """Map a driver error to a category and a closed cause; the message itself goes no further."""
    text = str(error).lower()
    if any(word in text for word in _UNRUNNABLE_WORDS):
        return _failed(
            DependencyFailureCategory.DAMAGED_DOWNLOAD, BrowserLaunchFailureCause.EXECUTABLE_UNRUNNABLE, error
        )
    if any(word in text for word in _TIMEOUT_WORDS):
        return _failed(DependencyFailureCategory.UNEXPECTED, BrowserLaunchFailureCause.TIMED_OUT, error)
    if any(word in text for word in _EXITED_WORDS):
        return _failed(DependencyFailureCategory.UNEXPECTED, BrowserLaunchFailureCause.BROWSER_EXITED, error)
    return _failed(DependencyFailureCategory.UNEXPECTED, BrowserLaunchFailureCause.DRIVER_FAILED, error)


async def launch_headless_browser(executable: Path, *, timeout_s: float) -> BrowserLaunchReading:
    """Start ``executable`` headless, read its version and close it, within ``timeout_s``.

    A browser that does not start is reported, never raised: a missing or
    unrunnable file reads as a damaged download, anything else as unexpected,
    each with the closed cause the full check records.
    """
    try:
        require_optional_extra(BROWSER_EXTRA)
    except MissingOptionalExtraError:
        return _failed(DependencyFailureCategory.NOT_IN_THIS_BUILD, BrowserLaunchFailureCause.DRIVER_UNAVAILABLE)
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright

    if not executable.is_file():
        return _failed(DependencyFailureCategory.DAMAGED_DOWNLOAD, BrowserLaunchFailureCause.EXECUTABLE_MISSING)
    try:
        async with asyncio.timeout(timeout_s), async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=str(executable),
                headless=True,
                timeout=timeout_s * 1000,
            )
            try:
                version = browser.version
            finally:
                await browser.close()
    except TimeoutError as exc:
        return _failed(DependencyFailureCategory.UNEXPECTED, BrowserLaunchFailureCause.TIMED_OUT, exc)
    except PlaywrightError as exc:
        return _driver_failure(exc)
    except OSError as exc:
        return _failed(DependencyFailureCategory.UNEXPECTED, BrowserLaunchFailureCause.DRIVER_UNAVAILABLE, exc)
    if not version:
        return _failed(DependencyFailureCategory.UNEXPECTED, BrowserLaunchFailureCause.NO_VERSION)
    return BrowserLaunchReading(version=version)
