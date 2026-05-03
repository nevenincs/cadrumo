"""BrowserSession factory for creating configured Playwright contexts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    ProxySettings,
    Response,
)
from playwright.async_api import (
    Error as PlaywrightError,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from .....core.config import Settings
from .....core.errors import AeatError, SiteHealthError
from .....core.logging import get_logger
from ..auth import BrowserContextProvisioner
from ._site_health import (
    _URL_ADAPTER,
    SiteHealthEvidence,
    SiteHealthState,
    SiteHealthStatus,
)
from ._site_health_probe import probe_response
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
        evasion_strategy: EvasionStrategy | None = None,
    ) -> None:
        """Initialize the BrowserSession.

        Args:
            playwright: The Playwright instance.
            settings: Application configuration settings.
            profile: The user profile to use.
            evasion_strategy: Optional evasion strategy (defaults to PlaywrightStealthEvasion).
        """
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
        """Create and configure a new Playwright BrowserContext.

        When ``provisioner`` is supplied, it can inject auth-provider-
        specific ``browser.new_context(...)`` kwargs and tag the
        resulting context after construction.

        Args:
            provisioner: Optional auth-provider hook used to decorate
                the new context call.

        Returns:
            A configured BrowserContext with evasion strategies
            applied and — when ``provisioner`` is supplied — the
            provider-specific context kwargs wired through at
            construction time.

        Raises:
            BrowserError: If the browser cannot be launched.
        """
        async with self._lifecycle_lock:
            if self._browser is not None:
                raise BrowserError(
                    "BrowserSession already owns a live browser; call close() before create_context() again"
                )
            logger.info("launching browser channel=%s", self.settings.aeat_browser_channel)
            try:
                proxy: ProxySettings | None = None
                if self.settings.aeat_proxy_url:
                    proxy = ProxySettings(server=self.settings.aeat_proxy_url)
                    if self.settings.aeat_proxy_username and self.settings.aeat_proxy_password_secret:
                        proxy["username"] = self.settings.aeat_proxy_username
                        proxy["password"] = self.settings.aeat_proxy_password_secret
                    if self.settings.aeat_proxy_bypass:
                        proxy["bypass"] = self.settings.aeat_proxy_bypass

                browser = await self.playwright.chromium.launch(
                    channel=self.settings.aeat_browser_channel,
                    headless=self.settings.aeat_browser_headless,
                    proxy=proxy,
                )
                self._browser = browser

                self.profile.ensure_storage_dir()
                effective_storage_state_path = storage_state_path or self.profile.storage_state_path

                context_kwargs: dict[str, Any] = {
                    "locale": self.profile.locale,
                    "timezone_id": self.profile.timezone_id,
                }
                if self.profile.user_agent:
                    context_kwargs["user_agent"] = self.profile.user_agent

                if effective_storage_state_path.exists():
                    context_kwargs["storage_state"] = str(effective_storage_state_path)

                if provisioner is not None:
                    context_kwargs.update(dict(provisioner.build_context_kwargs()))

                try:
                    context = await browser.new_context(**context_kwargs)
                finally:
                    # Keep provider materialised secrets live only for the
                    # exact Playwright construction boundary.
                    context_kwargs.pop("client_certificates", None)

                await self.evasion_strategy.apply(context)

                if provisioner is not None:
                    provisioner.annotate_context(context)

                return context
            except BrowserError:
                raise
            except Exception as exc:
                try:
                    await self._close_browser_locked()
                except BrowserError as cleanup_error:
                    logger.warning(
                        "failed to close partially created browser after context failure: %s",
                        cleanup_error,
                    )
                logger.error("failed to create browser context", exc_info=True)
                raise BrowserError(f"Failed to create browser context: {exc}") from exc

    async def close(self) -> None:
        """Close the retained Playwright browser, if any.

        Safe to call multiple times. The caller still owns any previously
        returned :class:`BrowserContext` objects and should close them before
        closing the session.

        Raises:
            BrowserError: If the retained browser cannot be closed. The
                browser handle is preserved so the caller can retry cleanup.
        """
        async with self._lifecycle_lock:
            await self._close_browser_locked()

    async def navigate(self, page: Page, url: str) -> Response | None:
        """Navigate ``page`` to ``url`` and probe the response health.

        This is an additive helper; direct ``page.goto`` calls remain
        legal but bypass the health probe. Stages that have migrated
        to :meth:`navigate` gain automatic classification of AEAT
        mantenimiento banners, WAF challenges, and rate-limit
        responses as typed :class:`SiteHealthError` instances.

        Args:
            page: The Playwright :class:`Page` to navigate.
            url: The target URL.

        Returns:
            The :class:`Response` Playwright yielded for the
            navigation (may be ``None`` when Playwright skipped the
            response — e.g. cached navigations).

        Raises:
            SiteHealthError: Either when the parser suite classifies
                the response as non-OK, or when the underlying
                ``page.goto`` fails with a transport-level error
                (DNS / TCP / TLS / Playwright timeout). In the latter
                case the error carries a sentinel HTTP status of
                ``599`` and a ``transport-error:<exc-type>`` marker.
        """
        try:
            response = await page.goto(url)
        except PlaywrightTimeoutError as exc:
            logger.warning(
                "browser navigate: timeout url=%s exc_type=%s",
                url,
                type(exc).__name__,
                exc_info=True,
            )
            raise SiteHealthError(status=self._build_unreachable_status(url, exc)) from exc
        except PlaywrightError as exc:
            logger.warning(
                "browser navigate: transport error url=%s exc_type=%s",
                url,
                type(exc).__name__,
                exc_info=True,
            )
            raise SiteHealthError(status=self._build_unreachable_status(url, exc)) from exc

        http_status = response.status if response is not None else 599
        headers_raw = dict(response.headers) if response is not None else {}
        html = await page.content()

        result = probe_response(
            url,
            http_status,
            headers_raw,
            html,
            rate_limit_retry_after_default=self.settings.site_health_rate_limit_retry_after_default,
        )
        if result is not None:
            raise SiteHealthError(status=result)
        return response

    @staticmethod
    def _build_unreachable_status(url: str, exc: BaseException) -> SiteHealthStatus:
        """Compose an UNREACHABLE :class:`SiteHealthStatus` from ``exc``.

        Args:
            url: The target URL that failed to load.
            exc: The transport-layer exception raised by Playwright.

        Returns:
            A populated :class:`SiteHealthStatus` carrying state
            :attr:`SiteHealthState.UNREACHABLE`, HTTP status ``599``
            (sentinel within the bounded 100..599 range), and a
            ``transport-error:<exc-type>`` detected marker.
        """
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

    async def _close_browser_locked(self) -> None:
        """Close the retained browser while the lifecycle lock is held."""
        browser = self._browser
        if browser is None:
            return
        try:
            await browser.close()
        except Exception as exc:
            logger.warning("failed to close retained browser", exc_info=True)
            raise BrowserError("Failed to close retained browser") from exc
        self._browser = None
