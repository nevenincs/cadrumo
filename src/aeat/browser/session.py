"""BrowserSession factory for creating configured Playwright contexts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    ProxySettings,
    Response,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from aeat.config import Settings
from aeat.errors import AeatError, SiteHealthError
from aeat.logging import get_logger
from aeat.status import (
    SiteHealthEvidence,
    SiteHealthState,
    SiteHealthStatus,
)
from aeat.status._site_health import _URL_ADAPTER

from ._site_health_probe import probe_response
from .evasion import EvasionStrategy, PlaywrightStealthEvasion
from .profile import Profile

if TYPE_CHECKING:
    from aeat.auth import LoadedCertificate

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
        auth_backend: LoadedCertificate | None = None,
        evasion_strategy: EvasionStrategy | None = None,
    ) -> None:
        """Initialize the BrowserSession.

        Args:
            playwright: The Playwright instance.
            settings: Application configuration settings.
            profile: The user profile to use.
            auth_backend: Optional loaded certificate for client-auth sessions.
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

            self.profile.ensure_storage_dir()

            context_kwargs: dict[str, Any] = {
                "locale": self.profile.locale,
                "timezone_id": self.profile.timezone_id,
            }
            if self.profile.user_agent:
                context_kwargs["user_agent"] = self.profile.user_agent

            # Playwright will fail if storage_state points to an empty string or invalid JSON
            context_kwargs["storage_state"] = str(self.profile.storage_state_path)

            if self.auth_backend is not None:
                from aeat.auth._certificate_backends._playwright_context import (
                    build_client_certificates_kwarg,
                )

                base = urlsplit(self.settings.aeat_base_url)
                origin = f"{base.scheme}://{base.netloc}"
                context_kwargs["client_certificates"] = build_client_certificates_kwarg(
                    self.auth_backend,
                    origin,
                )

            context = await browser.new_context(**context_kwargs)

            if self.auth_backend is not None:
                from aeat.auth._certificate_backends._playwright_context import (
                    mark_context_with_certificate,
                )

                mark_context_with_certificate(self.auth_backend, context)

            # Apply evasion strategy
            await self.evasion_strategy.apply(context)

            return context
        except Exception as e:
            logger.error("Failed to create browser context: %s", e)
            raise BrowserError(f"Failed to create browser context: {e}") from e

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
            raise SiteHealthError(status=self._build_unreachable_status(url, exc)) from exc
        except Exception as exc:
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
