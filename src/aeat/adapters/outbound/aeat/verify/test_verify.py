"""Unit tests for :func:`aeat.adapters.outbound.aeat.verify.verify_csv`.

Exercises the borrowed-vs-self-owned browser-session lifecycle of
:func:`verify_csv` using lightweight recording doubles that satisfy the
:class:`aeat.adapters.outbound.aeat.verify.VerifyBrowserSessionLike` and
:class:`aeat.adapters.outbound.aeat.verify.VerifyPlaywrightOwnerLike` shapes.
"""

from __future__ import annotations

from typing import cast

import pytest

import aeat.adapters.outbound.aeat.verify as verify_module
from aeat.adapters.outbound.aeat.verify import verify_csv
from aeat.domain.calculations.registry import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


class _RecordingKeyboard:
    """Recording double mirroring the Playwright keyboard surface."""

    def __init__(self) -> None:
        self.typed: list[str] = []
        self.pressed: list[str] = []

    async def type(self, value: str) -> None:
        self.typed.append(value)

    async def press(self, key: str) -> None:
        self.pressed.append(key)


class _RecordingPage:
    """Recording double mirroring the Playwright page surface used by ``verify_csv``."""

    def __init__(self, body: str) -> None:
        self._body = body
        self.goto_calls: list[str] = []
        self.fill_calls: list[tuple[str, str]] = []
        self.press_calls: list[tuple[str, str]] = []
        self.keyboard = _RecordingKeyboard()

    async def goto(self, url: str) -> None:
        self.goto_calls.append(url)

    async def fill(self, selector: str, value: str) -> None:
        self.fill_calls.append((selector, value))

    async def press(self, selector: str, key: str) -> None:
        self.press_calls.append((selector, key))

    async def content(self) -> str:
        return self._body


class _RecordingContext:
    """Recording double for a Playwright browser context, returning a fixed page."""

    def __init__(self, page: _RecordingPage) -> None:
        self._page = page
        self.close_calls = 0

    async def new_page(self) -> _RecordingPage:
        return self._page

    async def close(self) -> None:
        self.close_calls += 1


class _RecordingBrowserSession:
    """Recording double satisfying the ``VerifyBrowserSessionLike`` shape consumed by ``verify_csv``."""

    def __init__(self, body: str) -> None:
        self.page = _RecordingPage(body)
        self.context = _RecordingContext(self.page)
        self.create_context_calls = 0
        self.close_calls = 0

    async def create_context(self) -> _RecordingContext:
        self.create_context_calls += 1
        return self.context

    async def close(self) -> None:
        self.close_calls += 1


class _RecordingPlaywrightOwner:
    """Recording double satisfying the ``VerifyPlaywrightOwnerLike`` lifecycle shape."""

    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop(self) -> None:
        self.stop_calls += 1


@pytest.mark.asyncio
async def test_verify_csv_does_not_close_borrowed_browser_session() -> None:
    """Borrowed sessions remain caller-owned."""
    session = _RecordingBrowserSession("<html>documento válido</html>")

    result = await verify_csv(" abcd1234 ", browser=cast(verify_module.VerifyBrowserSessionLike, session))

    assert result is True
    assert session.create_context_calls == 1
    assert session.context.close_calls == 1
    assert session.close_calls == 0
    assert session.page.goto_calls == [verify_module._VERIFY_URL]


@pytest.mark.asyncio
async def test_verify_csv_closes_self_owned_session_and_playwright() -> None:
    """Self-owned sessions must honor the new BrowserSession close contract."""
    session = _RecordingBrowserSession("<html>documento desconocido</html>")
    playwright_owner = _RecordingPlaywrightOwner()
    session_like = cast(verify_module.VerifyBrowserSessionLike, session)
    playwright_like = cast(verify_module.VerifyPlaywrightOwnerLike, playwright_owner)

    async def _factory() -> tuple[verify_module.VerifyBrowserSessionLike, verify_module.VerifyPlaywrightOwnerLike]:
        return session_like, playwright_like

    original_factory = verify_module.DEFAULT_BROWSER_SESSION_FACTORY
    verify_module.DEFAULT_BROWSER_SESSION_FACTORY = cast(verify_module.VerifyBrowserSessionFactory, _factory)
    try:
        result = await verify_module.verify_csv("ABCD1234EFGH5678")
    finally:
        verify_module.DEFAULT_BROWSER_SESSION_FACTORY = original_factory

    assert result is False
    assert session.create_context_calls == 1
    assert session.context.close_calls == 1
    assert session.close_calls == 1
    assert playwright_owner.stop_calls == 1


def test_verify_csv_guard_rejects_non_read_method() -> None:
    with pytest.raises(RegistryValidationError, match="remote write method"):
        verify_module._assert_verify_http("POST", verify_module._VERIFY_URL)


def test_verify_csv_guard_rejects_mutating_action() -> None:
    with pytest.raises(RegistryValidationError, match="browser action token"):
        verify_module._assert_verify_action("Presentar declaracion")
