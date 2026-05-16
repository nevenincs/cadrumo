"""Default browser-session factory for auth providers.

Auth providers accept a ``BrowserSessionFactory`` — an async callable
that returns a ``BrowserSessionLike``. The default factory wires
the auth workflow end-to-end by supplying a Playwright-backed
session, while
:func:`aeat.adapters.outbound.aeat.auth.select_provider` continues to
accept ``browser_session_factory=None`` so tests can inject their own
in-process implementations.

This module provides:

* :class:`DefaultBrowserSession` — a ``BrowserSessionLike`` wrapper
  that owns a ``Playwright`` instance + :class:`BrowserSession`
  pair. Its ``close()`` tears down both.
* :func:`default_browser_session_factory` — the async callable that
  matches :class:`aeat.adapters.outbound.aeat.auth.BrowserSessionFactory` and yields a
  ``DefaultBrowserSession`` on demand.

The CLI wires this factory into ``select_provider`` so
the auth workflow works in production, while tests keep
injecting their own in-process implementations.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .....core.logging import get_logger
from .profile import Profile
from .session import BrowserSession

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright, Response

    from .....core.config import Settings


logger = get_logger(__name__)


class DefaultBrowserSession:
    """``BrowserSessionLike`` wrapper that owns its own Playwright.

    Auth providers receive a ``BrowserSessionLike`` but should not need
    to know whether the backing Playwright runtime was started
    specifically for this session or re-used across a longer-running
    process. ``DefaultBrowserSession`` lets the first case work cleanly:
    it constructs Playwright when the factory is called, and tears it
    down in ``close()``.
    """

    def __init__(
        self,
        playwright: Playwright,
        session: BrowserSession,
    ) -> None:
        self._playwright = playwright
        self._session = session
        self._close_lock = asyncio.Lock()
        self._closed = False

    @property
    def profile(self) -> Profile:
        return self._session.profile

    async def create_context(
        self,
        *,
        provisioner: Any | None = None,
        storage_state_path: Path | None = None,
        storage_state: dict[str, Any] | None = None,
    ) -> BrowserContext:
        return await self._session.create_context(
            provisioner=provisioner,
            storage_state_path=storage_state_path,
            storage_state=storage_state,
        )

    async def navigate(self, page: Page, url: str) -> Response | None:
        """Navigate through the central BrowserSession health-probed path."""

        return await self._session.navigate(page, url)

    async def close(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            try:
                await self._session.close()
            finally:
                try:
                    await self._playwright.stop()
                except Exception:  # Playwright stop() exception surface is undocumented; teardown must not abort
                    logger.warning("default_browser_session: playwright stop failed", exc_info=True)
                self._closed = True


async def default_browser_session_factory(settings: Settings) -> DefaultBrowserSession:
    """Start Playwright and return a wrapped :class:`BrowserSession`.

    The returned object satisfies
    :class:`aeat.adapters.outbound.aeat.auth.BrowserSessionLike` and owns its Playwright
    instance for the full lifetime. Call ``await session.close()``
    when you are done — auth providers already do this in their
    ``close()`` path.
    """
    from ....application.workflow._models import resolve_active_bucket_id

    # This factory is reachable from the diagnostic browser-connectivity
    # probe under `aeat config status`, so a missing active profile MUST
    # NOT raise here: the probe is exactly what an operator runs to
    # diagnose a missing-profile condition. The sentinel label keeps
    # the Profile model satisfied without pretending to be a real
    # profile.
    profile_name = resolve_active_bucket_id() or "diagnostic-probe"
    # Profile.storage_state_path is superseded by every auth-provider
    # passing an explicit kind-namespaced storage_state_path to
    # BrowserSession.create_context(). The value here is a fallback
    # for hypothetical future callers that do not override it; no
    # shipping provider currently relies on it.
    storage_state_path = settings.aeat_token_dir / f"{profile_name}-storage.json"
    profile = Profile(name=profile_name, storage_state_path=storage_state_path)
    return await create_browser_session(settings, profile)


async def create_browser_session(settings: Settings, profile: Profile) -> DefaultBrowserSession:
    """Start Playwright and return a wrapped :class:`BrowserSession` for ``profile``."""

    playwright = await _start_playwright()
    try:
        session = BrowserSession(
            playwright=playwright,
            settings=settings,
            profile=profile,
        )
        return DefaultBrowserSession(playwright=playwright, session=session)
    except BaseException:
        # Playwright.start() spawned a subprocess and opened pipes; any
        # exception between here and the successful return leaks those
        # resources. Mirror the teardown DefaultBrowserSession.close()
        # performs on the happy path.
        try:
            await playwright.stop()
        except Exception as stop_exc:
            logger.debug(
                "browser factory: playwright.stop() during error teardown failed (%s)",
                stop_exc,
                exc_info=True,
            )
        raise


@asynccontextmanager
async def shared_playwright_runtime() -> AsyncIterator[Playwright]:
    """Yield a centrally owned Playwright runtime for bulk browser workflows."""

    playwright = await _start_playwright()
    try:
        yield playwright
    finally:
        try:
            await playwright.stop()
        except Exception as stop_exc:
            logger.debug(
                "browser factory: playwright.stop() during runtime teardown failed (%s)",
                stop_exc,
                exc_info=True,
            )


@asynccontextmanager
async def opened_browser_page(
    playwright: Playwright,
    settings: Settings,
    profile: Profile,
    *,
    provisioner: Any | None = None,
    storage_state_path: Path | None = None,
    storage_state: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[Page, BrowserContext]]:
    """Yield a central :class:`BrowserSession` page/context pair and close both."""

    browser_session = BrowserSession(playwright=playwright, settings=settings, profile=profile)
    context = await browser_session.create_context(
        provisioner=provisioner,
        storage_state_path=storage_state_path,
        storage_state=storage_state,
    )
    try:
        page = await context.new_page()
        yield page, context
    finally:
        try:
            await context.close()
        except Exception as close_exc:
            logger.debug(
                "browser factory: context.close() during teardown failed (%s)",
                close_exc,
                exc_info=True,
            )
        await browser_session.close()


async def _start_playwright() -> Playwright:
    """Start the single browser-base Playwright runtime."""

    from playwright.async_api import async_playwright

    playwright_manager = async_playwright()
    return await playwright_manager.start()


__all__ = [
    "DefaultBrowserSession",
    "create_browser_session",
    "default_browser_session_factory",
    "opened_browser_page",
    "shared_playwright_runtime",
]
