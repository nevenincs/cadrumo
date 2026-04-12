"""BrowserSession factory for creating configured Playwright contexts."""

from __future__ import annotations

from typing import Any

from playwright.async_api import BrowserContext, Playwright, ProxySettings

from aeat.config import Settings
from aeat.errors import AeatError
from aeat.logging import get_logger

from .evasion import EvasionStrategy, PlaywrightStealthEvasion
from .profile import Profile

logger = get_logger(__name__)


class BrowserError(AeatError):
    """Base class for browser-related errors."""

    pass


class BrowserSession:
    """Factory and manager for Playwright browser contexts."""

    def __init__(
        self,
        playwright: Playwright,
        settings: Settings,
        profile: Profile,
        auth_backend: Any | None = None,
        evasion_strategy: EvasionStrategy | None = None,
    ) -> None:
        """Initialize the BrowserSession.

        Args:
            playwright: The Playwright instance.
            settings: Application configuration settings.
            profile: The user profile to use.
            auth_backend: Optional authentication backend (from feature #8).
            evasion_strategy: Optional evasion strategy (defaults to PlaywrightStealthEvasion).
        """
        self.playwright = playwright
        self.settings = settings
        self.profile = profile
        self.auth_backend = auth_backend
        self.evasion_strategy = evasion_strategy or PlaywrightStealthEvasion()

    async def create_context(self) -> BrowserContext:
        """Create and configure a new Playwright BrowserContext.

        Returns:
            A configured BrowserContext with evasion strategies applied.

        Raises:
            BrowserError: If the browser cannot be launched.
        """
        logger.info("Launching browser with channel: %s", self.settings.aeat_browser_channel)
        try:
            # Prepare proxy settings
            proxy: ProxySettings | None = None
            if self.settings.aeat_proxy_url:
                proxy_dict: dict[str, str] = {"server": self.settings.aeat_proxy_url}
                if self.settings.aeat_proxy_username and self.settings.aeat_proxy_password_secret:
                    proxy_dict["username"] = self.settings.aeat_proxy_username
                    proxy_dict["password"] = self.settings.aeat_proxy_password_secret
                if self.settings.aeat_proxy_bypass:
                    proxy_dict["bypass"] = self.settings.aeat_proxy_bypass
                proxy = proxy_dict  # type: ignore

            browser = await self.playwright.chromium.launch(
                channel=self.settings.aeat_browser_channel,
                headless=self.settings.aeat_browser_headless,
                proxy=proxy,
            )

            self.profile.ensure_storage_dir()

            context_kwargs: dict[str, Any] = {
                "locale": self.profile.locale,
                "timezone_id": self.profile.timezone_id,
            }
            if self.profile.user_agent:
                context_kwargs["user_agent"] = self.profile.user_agent

            # Playwright will fail if storage_state points to an empty string or invalid JSON
            context_kwargs["storage_state"] = str(self.profile.storage_state_path)

            context = await browser.new_context(**context_kwargs)

            # Apply evasion strategy
            await self.evasion_strategy.apply(context)

            # Apply auth backend if provided (stub for #8)
            if self.auth_backend:
                logger.info("Auth backend provided, applying certificate auth (stub).")
                pass

            return context
        except Exception as e:
            logger.error("Failed to create browser context: %s", e)
            raise BrowserError(f"Failed to create browser context: {e}") from e
