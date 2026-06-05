"""Unit tests for browser evasion strategies."""

from __future__ import annotations

from typing import cast

import pytest
from playwright.async_api import BrowserContext

from ..evasion import PlaywrightStealthEvasion

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class RecordingContext:
    """Minimal Playwright BrowserContext stand-in for stealth application.

    ``playwright_stealth.Stealth.apply_stealth_async`` only needs an awaitable
    ``add_init_script`` method and accepts arbitrary attribute assignment for
    its applied-marker. This concrete context satisfies that contract.
    """

    def __init__(self) -> None:
        self.init_scripts: list[str] = []

    async def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)


@pytest.mark.asyncio
async def test_playwright_stealth_evasion_applies_init_script() -> None:
    """``PlaywrightStealthEvasion`` must drive the 2.x ``Stealth`` class API."""
    evasion = PlaywrightStealthEvasion()
    context = RecordingContext()

    await evasion.apply(cast(BrowserContext, context))

    assert context.init_scripts, "Stealth init script was not injected into the context"
    assert any("navigator" in script.lower() or "webdriver" in script.lower() for script in context.init_scripts)
