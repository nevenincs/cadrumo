"""Minimal type stubs for ``playwright_stealth``.

Stubs cover the single call site in
``aeat.adapters.outbound.aeat.browser.evasion``.
"""

from playwright.async_api import BrowserContext

class Stealth:
    def __init__(self) -> None: ...
    async def apply_stealth_async(self, context: BrowserContext) -> None: ...
