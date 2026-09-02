"""Playwright browser-session manager for AEAT outbound adapters.

:class:`BrowserSession` is the concrete browser runtime behind the
application auth providers and live Sede readers. It creates one
Playwright ``BrowserContext`` at a time from a :class:`Profile`, optional
decrypted in-memory storage state, and an optional
:class:`adapters.outbound.aeat.auth.BrowserContextProvisioner`.
Certificate auth passes a
:class:`adapters.outbound.aeat.auth.CertificateContextProvisioner` so
the AEAT origin receives the configured PKCS#12 certificate at context
construction time.

The session also applies the configured :class:`EvasionStrategy` and exposes
:meth:`BrowserSession.navigate`, the health-probed navigation path that turns
AEAT maintenance, WAF, rate-limit, and transport failures into typed
:class:`SiteHealthStatus` or :class:`BrowserError` outcomes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # playwright is the optional `browser` extra; keep its types out of module
    # load so this module imports without it. The only runtime use,
    # ProxySettings, is imported lazily at its call site (behind the factory's
    # require_optional_extra(BROWSER_EXTRA) guard).
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        Playwright,
        ProxySettings,
        Response,
    )

from .....core.async_cleanup import await_cancellation_complete
from .....core.config import Settings
from .....core.errors.hierarchy import SiteHealthError, SiteHealthState
from .....core.logging import get_logger
from .....core.operator_action_enums import NoRecoveryOutcome
from .....core.time.clock import now
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from ..auth.providers import BrowserContextProvisioner
from ._site_health_probe import probe_response
from .errors import (
    BrowserError,
    BrowserFailureMode,
    BrowserPreconditionCondition,
    browser_no_action_verdict,
)
from .evasion import EvasionStrategy, PlaywrightStealthEvasion
from .profile import Profile
from .site_health_records import (
    SiteHealthEvidence,
    SiteHealthStatus,
    parse_site_health_url,
)

logger = get_logger(__name__)


class BrowserSession:
    """Factory and lifecycle manager for one Playwright browser context.

    A session owns at most one live browser until :meth:`close` runs. Auth
    providers use :meth:`create_context` to combine :class:`Profile` defaults,
    encrypted-session storage state, and provider-owned browser context kwargs
    such as client-certificate provisioning.
    """

    def __init__(
        self,
        playwright: Playwright,
        settings: Settings,
        profile: Profile,
        evasion_strategy: EvasionStrategy | None = None,
    ) -> None:
        """Initialize the browser session.

        Args:
            playwright: The Playwright instance.
            settings: Application configuration settings.
            profile: The :class:`Profile` carrying browser locale and timezone.
            evasion_strategy: Optional :class:`EvasionStrategy`; defaults to
                :class:`PlaywrightStealthEvasion`.
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
        storage_state: Mapping[str, object] | None = None,
    ) -> BrowserContext:
        """Create and configure a new Playwright BrowserContext.

        When ``provisioner`` is supplied, it injects auth-provider-specific
        ``browser.new_context(...)`` kwargs. Certificate auth uses this hook
        through
        :class:`adapters.outbound.aeat.auth.CertificateContextProvisioner`;
        Cl@ve Móvil usually passes only persisted in-memory storage state.

        Args:
            provisioner: Optional :class:`BrowserContextProvisioner` used to
                decorate the new context call.
            storage_state: Optional in-memory storage state mapping passed
                directly to ``browser.new_context``.

        Returns:
            A configured BrowserContext with evasion strategies
            applied and — when ``provisioner`` is supplied — the
            provider-specific context kwargs wired through at
            construction time.

        Raises:
            BrowserError: If the browser cannot be launched, the context cannot
                be created, evasion setup fails, or this session already owns a
                live browser.
        """
        async with self._lifecycle_lock:
            if self._browser is not None:
                raise BrowserError(
                    "Browser session already owns a live browser",
                    failure_mode=BrowserFailureMode.SESSION_BUSY,
                    context={"profile": self.profile.name},
                    precondition_verdict=browser_no_action_verdict(
                        condition=BrowserPreconditionCondition.SESSION_AVAILABLE,
                        facts={"browser_session_available": False},
                        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                    ),
                )
            logger.info(
                "browser context create starting profile=%s channel=%s headless=%s has_proxy=%s",
                self.profile.name,
                self.settings.cadrumo_browser_channel,
                self.settings.cadrumo_browser_headless,
                bool(self.settings.cadrumo_proxy_url),
            )
            proxy = self._build_proxy_settings()
            browser = await self._launch_chromium(proxy)
            self._browser = browser
            try:
                context_kwargs = self._build_context_kwargs(
                    storage_state=storage_state,
                    provisioner=provisioner,
                )
                context = await await_cancellation_complete(
                    self._create_playwright_context(browser, context_kwargs),
                    task_name="cadrumo-browser-context-create",
                )
                await self._apply_evasion(context)
                logger.info("browser context create succeeded profile=%s", self.profile.name)
                return context
            except asyncio.CancelledError as cancellation:
                await await_cancellation_complete(
                    self._close_after_context_failure(),
                    task_name="cadrumo-browser-context-cancel-cleanup",
                    cancellation=cancellation,
                )
                raise cancellation from None
            except BrowserError:
                await self._close_after_context_failure()
                raise
            except Exception as exc:
                await self._close_after_context_failure()
                logger.error(
                    "browser context preparation failed failure_mode=%s profile=%s exc_type=%s",
                    BrowserFailureMode.CONTEXT_CREATE_FAILED,
                    self.profile.name,
                    type(exc).__name__,
                    exc_info=True,
                )
                raise BrowserError(
                    "Browser context preparation failed",
                    failure_mode=BrowserFailureMode.CONTEXT_CREATE_FAILED,
                    context={"profile": self.profile.name, "cause_type": type(exc).__name__},
                    precondition_verdict=browser_no_action_verdict(
                        condition=BrowserPreconditionCondition.CONTEXT_CREATABLE,
                        facts={"browser_context_creatable": False},
                        outcome=NoRecoveryOutcome.SAFETY,
                    ),
                ) from exc

    def _build_proxy_settings(self) -> ProxySettings | None:
        """Translate the settings's proxy block into a Playwright ProxySettings record."""
        if not self.settings.cadrumo_proxy_url:
            return None
        from playwright.async_api import ProxySettings

        proxy = ProxySettings(server=self.settings.cadrumo_proxy_url)
        if self.settings.cadrumo_proxy_username and self.settings.cadrumo_proxy_password_secret is not None:
            proxy["username"] = self.settings.cadrumo_proxy_username
            proxy["password"] = self.settings.cadrumo_proxy_password_secret.get_secret_value()
        if self.settings.cadrumo_proxy_bypass:
            proxy["bypass"] = self.settings.cadrumo_proxy_bypass
        return proxy

    async def _launch_chromium(self, proxy: ProxySettings | None) -> Browser:
        """Launch Chromium with the profile's channel/headless/proxy config; raise BrowserError on failure."""
        try:
            return await self.playwright.chromium.launch(
                channel=self.settings.cadrumo_browser_channel,
                headless=self.settings.cadrumo_browser_headless,
                proxy=proxy,
            )
        except Exception as exc:
            logger.error(
                "browser launch failed failure_mode=%s profile=%s channel=%s headless=%s has_proxy=%s exc_type=%s",
                BrowserFailureMode.BROWSER_LAUNCH_FAILED,
                self.profile.name,
                self.settings.cadrumo_browser_channel,
                self.settings.cadrumo_browser_headless,
                bool(self.settings.cadrumo_proxy_url),
                type(exc).__name__,
                exc_info=True,
            )
            raise BrowserError(
                "Browser launch failed",
                failure_mode=BrowserFailureMode.BROWSER_LAUNCH_FAILED,
                context={
                    "profile": self.profile.name,
                    "channel": self.settings.cadrumo_browser_channel,
                    "headless": self.settings.cadrumo_browser_headless,
                    "has_proxy": bool(self.settings.cadrumo_proxy_url),
                    "cause_type": type(exc).__name__,
                },
                precondition_verdict=browser_no_action_verdict(
                    condition=BrowserPreconditionCondition.BROWSER_LAUNCHABLE,
                    facts={"browser_launchable": False},
                    outcome=NoRecoveryOutcome.SAFETY,
                ),
            ) from exc

    def _build_context_kwargs(
        self,
        *,
        storage_state: Mapping[str, object] | None,
        provisioner: BrowserContextProvisioner | None,
    ) -> dict[str, Any]:
        """Compose ``browser.new_context(**kwargs)`` from explicit storage and provisioner inputs.

        ``dict[str, Any]`` is the irreducible adapter shape: the dict is
        spread into ``new_context(**context_kwargs)`` whose typed kwargs
        are heterogeneous (storage_state, proxy, viewport, ...).
        Narrowing to ``object`` breaks the spread under Playwright's
        stubs; this is a third-party-API boundary where ``Any`` is the
        right type.
        """
        context_kwargs: dict[str, Any] = {
            "locale": self.profile.locale,
            "timezone_id": self.profile.timezone_id,
            # Chromium writes an attachment's bytes to its own OS-managed
            # temp folder unconditionally the moment a download starts --
            # `download.cancel()` only stops an in-flight transfer, it does
            # not retroactively un-write bytes already streamed to disk
            # before cancellation lands (measured: several hundred KB of a
            # multi-MB payload landed in a `.crdownload` file within one
            # event-loop tick of `expect_download()` yielding). Refusing
            # downloads at the context level closes that gap outright:
            # Playwright's download event still fires and `download.url` is
            # still populated (measured: both survive `accept_downloads`
            # False), but Chromium never persists a byte anywhere. No
            # production flow in this adapter reads a browser-triggered
            # download from disk -- the sole consumer,
            # `capture_submitted_file_artefact`, already re-fetches the
            # captured URL in-memory via `context.request` -- so this is a
            # zero-behaviour-change default project-wide
            # (sensitive-financial-data-secure-storage-only).
            "accept_downloads": False,
        }
        if self.profile.user_agent:
            context_kwargs["user_agent"] = self.profile.user_agent
        if storage_state is not None:
            context_kwargs["storage_state"] = storage_state
        if provisioner is not None:
            context_kwargs.update(dict(provisioner.build_context_kwargs()))
        return context_kwargs

    # ADAPTER-INTERNAL-ALIAS-RATIONALE-PLAYWRIGHT-CONTEXT-KWARGS: context_kwargs
    # is Playwright's free-shape new_context payload (storage_state, certs, etc.);
    # the upstream stubs do not export a TypedDict for the assembled kwargs.
    async def _create_playwright_context(self, browser: Browser, context_kwargs: dict[str, Any]) -> BrowserContext:
        """Wrap ``browser.new_context(...)`` with the typed BrowserError envelope.

        Pops ``client_certificates`` from ``context_kwargs`` after the
        call so provider-materialised secrets stay live only for the
        exact Playwright construction boundary.
        """
        try:
            return await browser.new_context(**context_kwargs)
        except Exception as exc:
            logger.error(
                "browser context creation failed failure_mode=%s profile=%s locale=%s timezone=%s "
                "storage_state_source=%s exc_type=%s",
                BrowserFailureMode.CONTEXT_CREATE_FAILED,
                self.profile.name,
                self.profile.locale,
                self.profile.timezone_id,
                _storage_state_source(context_kwargs),
                type(exc).__name__,
                exc_info=True,
            )
            raise BrowserError(
                "Browser context creation failed",
                failure_mode=BrowserFailureMode.CONTEXT_CREATE_FAILED,
                context={
                    "profile": self.profile.name,
                    "locale": self.profile.locale,
                    "timezone_id": self.profile.timezone_id,
                    "storage_state_source": _storage_state_source(context_kwargs),
                    "cause_type": type(exc).__name__,
                },
                precondition_verdict=browser_no_action_verdict(
                    condition=BrowserPreconditionCondition.CONTEXT_CREATABLE,
                    facts={
                        "browser_context_creatable": False,
                        "storage_state_supplied": "storage_state" in context_kwargs,
                        "provisioner_supplied": "client_certificates" in context_kwargs,
                    },
                    outcome=NoRecoveryOutcome.SAFETY,
                ),
            ) from exc
        finally:
            context_kwargs.pop("client_certificates", None)

    async def _apply_evasion(self, context: BrowserContext) -> None:
        """Apply the evasion strategy to ``context`` with a typed BrowserError envelope."""
        try:
            await self.evasion_strategy.apply(context)
        except Exception as exc:
            logger.error(
                "browser evasion failed failure_mode=%s profile=%s evasion_strategy=%s exc_type=%s",
                BrowserFailureMode.EVASION_FAILED,
                self.profile.name,
                type(self.evasion_strategy).__name__,
                type(exc).__name__,
                exc_info=True,
            )
            raise BrowserError(
                "Browser evasion setup failed",
                failure_mode=BrowserFailureMode.EVASION_FAILED,
                context={
                    "profile": self.profile.name,
                    "evasion_strategy": type(self.evasion_strategy).__name__,
                    "cause_type": type(exc).__name__,
                },
                precondition_verdict=browser_no_action_verdict(
                    condition=BrowserPreconditionCondition.EVASION_APPLIED,
                    facts={"browser_evasion_applied": False},
                    outcome=NoRecoveryOutcome.SAFETY,
                ),
            ) from exc

    async def close(self) -> None:
        """Close the retained Playwright browser, if any.

        Safe to call multiple times. The caller still owns any previously
        returned :class:`BrowserContext` objects and should close them before
        closing the session.
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
            SiteHealthError: When the parser suite classifies the response as non-OK,
                or when ``page.goto`` fails with a transport-level error
                (DNS / TCP / TLS / Playwright timeout).
            BrowserError: When reading the page content after navigation fails.
        """
        logger.info("browser navigate starting url=%s", url)
        try:
            response = await page.goto(url)
        except PlaywrightTimeoutError as exc:
            logger.warning(
                "browser navigate: timeout url=%s exc_type=%s",
                url,
                type(exc).__name__,
                exc_info=True,
            )
            raise SiteHealthError(
                status=self._build_unreachable_status(
                    url,
                    exc,
                    failure_mode=BrowserFailureMode.NAVIGATION_TIMEOUT,
                ),
            ) from exc
        except PlaywrightError as exc:
            logger.warning(
                "browser navigate: transport error url=%s exc_type=%s",
                url,
                type(exc).__name__,
                exc_info=True,
            )
            raise SiteHealthError(
                status=self._build_unreachable_status(
                    url,
                    exc,
                    failure_mode=BrowserFailureMode.NAVIGATION_TRANSPORT_ERROR,
                ),
            ) from exc

        http_status = response.status if response is not None else 599
        headers_raw = dict(response.headers) if response is not None else {}
        try:
            html = await page.content()
        except Exception as exc:
            logger.error(
                "browser navigate content read failed failure_mode=%s url=%s http_status=%s exc_type=%s",
                BrowserFailureMode.PAGE_CONTENT_FAILED,
                url,
                http_status,
                type(exc).__name__,
                exc_info=True,
            )
            raise BrowserError(
                "Navigated browser page content is unreadable",
                failure_mode=BrowserFailureMode.PAGE_CONTENT_FAILED,
                context={"url": url, "http_status": http_status, "cause_type": type(exc).__name__},
                precondition_verdict=browser_no_action_verdict(
                    condition=BrowserPreconditionCondition.PAGE_CONTENT_READABLE,
                    facts={"browser_page_content_readable": False},
                    outcome=NoRecoveryOutcome.SAFETY,
                ),
            ) from exc

        result = probe_response(
            url,
            http_status,
            headers_raw,
            html,
            rate_limit_retry_after_default=self.settings.site_health_rate_limit_retry_after_default,
        )
        if result is not None:
            logger.warning(
                "browser navigate site health failure failure_mode=%s url=%s state=%s http_status=%s markers=%s",
                BrowserFailureMode.SITE_HEALTH_NON_OK,
                url,
                result.state,
                result.evidence.http_status,
                result.evidence.detected_markers,
            )
            raise SiteHealthError(status=result)
        logger.info("browser navigate succeeded url=%s http_status=%s", url, http_status)
        return response

    @staticmethod
    def _build_unreachable_status(
        url: str,
        exc: BaseException,
        *,
        failure_mode: BrowserFailureMode,
    ) -> SiteHealthStatus:
        """Compose an UNREACHABLE :class:`SiteHealthStatus` from ``exc``.

        Args:
            url: The target URL that failed to load.
            exc: The transport-layer exception raised by Playwright.
            failure_mode: The :class:`BrowserFailureMode` variant that
                describes the kind of transport failure; embedded as a
                ``failure-mode:<value>`` marker in the returned status.

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
                url=parse_site_health_url(url),
                http_status=599,
                html_fragment="",
                detected_markers=(f"failure-mode:{failure_mode.value}", f"transport-error:{exc_type_name}"),
            ),
            observed_at=now(),
        )

    async def _close_after_context_failure(self) -> None:
        """Best-effort cleanup for failed context creation paths."""
        try:
            await self._close_browser_locked()
        except BrowserError as cleanup_error:
            logger.warning(
                "failed to close partially created browser after context failure: %s",
                cleanup_error,
            )

    async def _close_browser_locked(self) -> None:
        """Close the retained browser while the lifecycle lock is held."""
        browser = self._browser
        if browser is None:
            return
        try:
            await browser.close()
        except Exception as exc:
            logger.warning(
                "failed to close retained browser failure_mode=%s profile=%s exc_type=%s",
                BrowserFailureMode.BROWSER_CLOSE_FAILED,
                self.profile.name,
                type(exc).__name__,
                exc_info=True,
            )
            raise BrowserError(
                "Failed to close retained browser",
                failure_mode=BrowserFailureMode.BROWSER_CLOSE_FAILED,
                context={"profile": self.profile.name, "cause_type": type(exc).__name__},
                precondition_verdict=browser_no_action_verdict(
                    condition=BrowserPreconditionCondition.BROWSER_CLOSEABLE,
                    facts={"browser_closeable": False},
                    outcome=NoRecoveryOutcome.SAFETY,
                ),
            ) from exc
        self._browser = None


def _storage_state_source(context_kwargs: Mapping[str, object]) -> str:
    """Describe the storage-state input without logging secret material."""
    return "inline" if "storage_state" in context_kwargs else "none"
