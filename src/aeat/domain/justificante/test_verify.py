"""Unit tests for :func:`aeat.justificante.verify_csv`."""

from __future__ import annotations

from typing import cast

import pytest

from . import _verify as verify_module
from ._verify import verify_csv

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class _FakeKeyboard:
    def __init__(self) -> None:
        self.typed: list[str] = []
        self.pressed: list[str] = []

    async def type(self, value: str) -> None:
        self.typed.append(value)

    async def press(self, key: str) -> None:
        self.pressed.append(key)


class _FakePage:
    def __init__(self, body: str) -> None:
        self._body = body
        self.goto_calls: list[str] = []
        self.fill_calls: list[tuple[str, str]] = []
        self.press_calls: list[tuple[str, str]] = []
        self.keyboard = _FakeKeyboard()

    async def goto(self, url: str) -> None:
        self.goto_calls.append(url)

    async def fill(self, selector: str, value: str) -> None:
        self.fill_calls.append((selector, value))

    async def press(self, selector: str, key: str) -> None:
        self.press_calls.append((selector, key))

    async def content(self) -> str:
        return self._body


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.close_calls = 0

    async def new_page(self) -> _FakePage:
        return self._page

    async def close(self) -> None:
        self.close_calls += 1


class _FakeBrowserSession:
    def __init__(self, body: str) -> None:
        self.page = _FakePage(body)
        self.context = _FakeContext(self.page)
        self.create_context_calls = 0
        self.close_calls = 0

    async def create_context(self) -> _FakeContext:
        self.create_context_calls += 1
        return self.context

    async def close(self) -> None:
        self.close_calls += 1


class _FakePlaywrightOwner:
    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop(self) -> None:
        self.stop_calls += 1


@pytest.mark.asyncio
async def test_verify_csv_does_not_close_borrowed_browser_session() -> None:
    """Borrowed sessions remain caller-owned."""
    session = _FakeBrowserSession("<html>documento válido</html>")

    result = await verify_csv(" abcd1234 ", browser=cast(verify_module.BrowserSessionLike, session))

    assert result is True
    assert session.create_context_calls == 1
    assert session.context.close_calls == 1
    assert session.close_calls == 0
    assert session.page.goto_calls == [verify_module._VERIFY_URL]


@pytest.mark.asyncio
async def test_verify_csv_closes_self_owned_session_and_playwright() -> None:
    """Self-owned sessions must honor the new BrowserSession close contract."""
    session = _FakeBrowserSession("<html>documento desconocido</html>")
    playwright_owner = _FakePlaywrightOwner()
    session_like = cast(verify_module.BrowserSessionLike, session)
    playwright_like = cast(verify_module.PlaywrightOwnerLike, playwright_owner)

    async def _factory() -> tuple[verify_module.BrowserSessionLike, verify_module.PlaywrightOwnerLike]:
        return session_like, playwright_like

    original_factory = verify_module.DEFAULT_BROWSER_SESSION_FACTORY
    verify_module.DEFAULT_BROWSER_SESSION_FACTORY = cast(verify_module.BrowserSessionFactory, _factory)
    try:
        result = await verify_module.verify_csv("ABCD1234EFGH5678")
    finally:
        verify_module.DEFAULT_BROWSER_SESSION_FACTORY = original_factory

    assert result is False
    assert session.create_context_calls == 1
    assert session.context.close_calls == 1
    assert session.close_calls == 1
    assert playwright_owner.stop_calls == 1
