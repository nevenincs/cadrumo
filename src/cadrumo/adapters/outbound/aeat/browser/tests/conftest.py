"""The Chromium a view test module's tests share, each in a context of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest_asyncio

from .view_page_support import launched_chromium

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from playwright.async_api import Browser


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def chromium() -> AsyncGenerator[Browser]:
    """One headless Chromium per module, launched on the module's event loop."""
    async with launched_chromium() as browser:
        yield browser
