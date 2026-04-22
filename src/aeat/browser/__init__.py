"""Browser automation subpackage for the AEAT client.

Provides the `BrowserSession` factory to manage Playwright contexts with
anti-bot evasion strategies and persistent profiles.

Example:
    ```python
    from pathlib import Path
    from playwright.async_api import async_playwright
    from ..config import load_settings
    from . import BrowserSession, Profile

    async def main():
        settings = load_settings()
        profile = Profile(name="test", storage_state_path=Path(".tokens/state.json"))

        async with async_playwright() as p:
            session = BrowserSession(playwright=p, settings=settings, profile=profile)
            context = await session.create_context()
            page = await context.new_page()
            await page.goto("https://sede.agenciatributaria.gob.es")
            await context.close()
    ```
"""

from __future__ import annotations

from ._factory import DefaultBrowserSession, default_browser_session_factory
from .evasion import EvasionStrategy, PlaywrightStealthEvasion
from .health import run_health_check
from .profile import Profile
from .session import BrowserError, BrowserSession

__all__ = [
    "BrowserError",
    "BrowserSession",
    "DefaultBrowserSession",
    "EvasionStrategy",
    "PlaywrightStealthEvasion",
    "Profile",
    "default_browser_session_factory",
    "run_health_check",
]
