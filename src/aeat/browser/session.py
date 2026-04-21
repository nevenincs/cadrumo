from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Response,
)
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ..auth._protocols import AEAT_CERTIFICATE_THUMBPRINT_MARKER
from ..errors import AeatError, SiteHealthError
from ..logging import get_logger
from ..status import SiteHealthEvidence, SiteHealthState, SiteHealthStatus
from ..status._site_health import _URL_ADAPTER
from ._site_health_probe import probe_response
from .evasion import EvasionStrategy, PlaywrightStealthEvasion
from .profile import Profile

if TYPE_CHECKING:
    from ..config import Settings

logger = get_logger(__name__)

BrowserContextProvisioner = Callable[[dict[str, Any]], None]
CERTIFICATE_THUMBPRINT_MARKER = AEAT_CERTIFICATE_THUMBPRINT_MARKER


class BrowserError(AeatError):
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
                proxy: dict[str, str] | None = None
                if self.settings.aeat_proxy_url:
                    proxy = {"server": self.settings.aeat_proxy_url}
                    if self.settings.aeat_proxy_username and self.settings.aeat_proxy_password_secret:
                        proxy["username"] = self.settings.aeat_proxy_username
                        proxy["password"] = self.settings.aeat_proxy_password_secret
                    if self.settings.aeat_proxy_bypass:
                        proxy["bypass"] = self.settings.aeat_proxy_bypass

                self._browser = await self.playwright.chromium.launch(
                    headless=self.settings.aeat_browser_headless,
                    channel=self.settings.aeat_browser_channel,
                    proxy=proxy,
                )

                context_kwargs: dict[str, Any] = {}
                if self.profile.user_agent is not None:
                    context_kwargs["user_agent"] = self.profile.user_agent
                if self.profile.locale is not None:
                    context_kwargs["locale"] = self.profile.locale
                if self.profile.timezone_id is not None:
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
                browser = self._browser
                if browser is not None:
                    try:
                        await browser.close()
                    except Exception as cleanup_exc:
                        logger.warning(
                            "BrowserSession cleanup after create_context failure failed: %s",
                            cleanup_exc,
                        )
                    finally:
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

    async def navigate(self, page: Page, url: str) -> Response | None:
        """Navigate a page and classify known AEAT site-health failures."""
        try:
            response = await page.goto(url)
        except PlaywrightTimeoutError as exc:
            raise SiteHealthError(status=self._build_unreachable_status(url, exc)) from exc
        except Exception as exc:
            raise SiteHealthError(status=self._build_unreachable_status(url, exc)) from exc

        http_status = response.status if response is not None else 599
        headers = dict(response.headers) if response is not None else {}
        html = await page.content()
        result = probe_response(
            url,
            http_status,
            headers,
            html,
            rate_limit_retry_after_default=self.settings.site_health_rate_limit_retry_after_default,
        )
        if result is not None:
            raise SiteHealthError(status=result)
        return response

    @staticmethod
    def _build_unreachable_status(url: str, exc: BaseException) -> SiteHealthStatus:
        """Translate a transport failure into a typed unreachable status."""
        exc_type_name = type(exc).__name__
        return SiteHealthStatus(
            state=SiteHealthState.UNREACHABLE,
            evidence=SiteHealthEvidence(
                url=_URL_ADAPTER.validate_python(url),
                http_status=599,
                html_fragment="",
                detected_markers=(f"transport-error:{exc_type_name}",),
            ),
            observed_at=datetime.now(tz=UTC),
        )
