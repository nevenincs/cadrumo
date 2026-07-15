"""Typed navigation-timeout outcome for the declaraciones register drive.

``capture_expedientes`` (the ``aeat app live expedientes pull`` verb) reaches
AEAT through ``DeclaracionesRegisterSession.walk`` -> ``_drive_search``, the same
form-drive helper :mod:`test_declarations_live` exercises against the real
sede. This suite drives the real ``_drive_search`` coroutine against a fake
Playwright ``Page`` whose ``goto`` raises the real
``playwright.async_api.TimeoutError`` alias, proving the production code maps
a navigation timeout to a typed, failure-mode-tagged :exc:`SedeNavigationError`
rather than leaking the raw Playwright exception.
"""

from __future__ import annotations

import pytest

from ..._playwright import PlaywrightTimeoutError
from .._declarations import _drive_search
from .._errors import SedeFailureMode, SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _TimeoutOnGotoPage:
    """Fake Playwright page whose ``goto`` times out like a stalled sede.

    Every other method the walker could reach is left unimplemented on
    purpose: ``_drive_search`` must raise before touching them.
    """

    url = ""

    async def goto(self, url: str, *, wait_until: str | None = None, timeout: int | None = None) -> None:
        raise PlaywrightTimeoutError(f"Timeout {timeout}ms exceeded navigating to {url!r}.")

    async def content(self) -> str:
        return ""


@pytest.mark.asyncio
async def test_navigation_timeout_raises_typed_navigation_error() -> None:
    """A goto timeout surfaces as a typed, non-leaking navigation failure."""
    page = _TimeoutOnGotoPage()

    with pytest.raises(SedeNavigationError) as exc_info:
        await _drive_search(page, modelo="100", ejercicio=2022)

    assert exc_info.value.failure_mode == SedeFailureMode.LIVE_NAVIGATION_FAILED
    assert exc_info.value.context is not None
    assert exc_info.value.context["stage"] == "listing_goto"
    assert exc_info.value.context["modelo"] == "100"
    assert exc_info.value.context["ejercicio"] == 2022
    # The raw Playwright exception is chained, never swallowed silently.
    assert isinstance(exc_info.value.__cause__, PlaywrightTimeoutError)
