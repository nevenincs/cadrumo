from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from playwright.async_api import (
    Browser,
    BrowserContext,
)

from ..logging import get_logger
from .evasion import EvasionStrategy, PlaywrightStealthEvasion
from .profile import Profile

if TYPE_CHECKING:
    from ..auth import BrowserContextLike
    from ..config import Settings

logger = get_logger(__name__)


@runtime_checkable
class BrowserContextProvisioner(Protocol):
    """Hook that decorates BrowserSession.create_context()."""

    def build_context_kwargs(self) -> Mapping[str, Any]: ...

    def annotate_context(self, context: BrowserContextLike) -> None: ...


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
                raise BrowserError("BrowserSession already owns a live browser")

            logger.info("Launching browser")
            try:
                self._browser = await self.playwright.chromium.launch(
                    headless=self.settings.aeat_browser_headless,
                    channel=self.settings.aeat_browser_channel,
                )

                context_kwargs: dict[str, Any] = {
                    "user_agent": self.settings.aeat_browser_user_agent,
                }

                effective_storage_state_path = storage_state_path or self.profile.storage_state_path
                if effective_storage_state_path and effective_storage_state_path.exists():
                    context_kwargs["storage_state"] = str(effective_storage_state_path)

                if provisioner is not None:
                    context_kwargs.update(dict(provisioner.build_context_kwargs()))

                context = await self._browser.new_context(**context_kwargs)

                if provisioner is not None:
                    provisioner.annotate_context(context)

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
                await self._browser.close()
                self._browser = None
