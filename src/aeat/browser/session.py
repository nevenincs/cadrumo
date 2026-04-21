from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from playwright.async_api import (
    Browser,
    BrowserContext,
)

from ..auth import AEAT_CERTIFICATE_THUMBPRINT_MARKER
from ..logging import get_logger
from .evasion import EvasionStrategy, PlaywrightStealthEvasion
from .profile import Profile

if TYPE_CHECKING:
    from ..config import Settings

logger = get_logger(__name__)

CERTIFICATE_THUMBPRINT_MARKER = AEAT_CERTIFICATE_THUMBPRINT_MARKER
BrowserContextProvisioner = Callable[[dict[str, Any]], None]


class BrowserError(Exception):
    """Base class for browser-related errors."""

    pass


class BrowserSession:
    """Owner of a Playwright Browser instance and its lifecycle."""

    def __init__(
        self,
        playwright: Any,
        settings: Settings,
        profile: Profile,
        evasion_strategy: EvasionStrategy | None = None,
    ) -> None:
        self.playwright = playwright
        self.settings = settings
        self.profile = profile
        self.evasion_strategy = evasion_strategy or PlaywrightStealthEvasion()
        self._browser: Browser | None = None
        self._lifecycle_lock = asyncio.Lock()

    async def create_context(
        self,
        *,
        provisioner: BrowserContextProvisioner | None = None,
        storage_state_path: Path | None = None,
    ) -> BrowserContext:
        """Create and configure a new Playwright BrowserContext."""
        async with self._lifecycle_lock:
            if self._browser is not None:
                raise BrowserError(
                    "BrowserSession already owns a live browser; call close() before create_context() again"
                )

            logger.info("Launching browser")
            try:
                self._browser = await self.playwright.chromium.launch(
                    headless=self.settings.aeat_browser_headless,
                    channel=self.settings.aeat_browser_channel,
                )

                context_kwargs: dict[str, Any] = {}
                if self.profile.user_agent:
                    context_kwargs["user_agent"] = self.profile.user_agent
                if self.profile.locale:
                    context_kwargs["locale"] = self.profile.locale
                if self.profile.timezone_id:
                    context_kwargs["timezone_id"] = self.profile.timezone_id

                effective_storage_state_path = storage_state_path or self.profile.storage_state_path
                if effective_storage_state_path and effective_storage_state_path.exists():
                    context_kwargs["storage_state"] = str(effective_storage_state_path)

                if provisioner is not None:
                    provisioner(context_kwargs)

                context = await self._browser.new_context(**context_kwargs)

                await self.evasion_strategy.apply(context)
                return context
            except Exception as exc:
                if self._browser is not None:
                    await self._browser.close()
                    self._browser = None
                raise BrowserError(f"Failed to create browser context: {exc}") from exc

    async def close(self) -> None:
        """Close the browser instance."""
        async with self._lifecycle_lock:
            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception as exc:
                    raise BrowserError(f"Failed to close retained browser: {exc}") from exc
                self._browser = None
