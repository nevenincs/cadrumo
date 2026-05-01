"""Default browser-session factory for auth providers (#285).

Auth providers accept a ``BrowserSessionFactory`` — an async callable
that returns a ``BrowserSessionLike``. Until this module, the only
production wiring was the live-test fixture that manually opened a
Playwright instance and built a :class:`BrowserSession`. That left
``aeat auth login`` unable to run end-to-end because
:func:`aeat.adapters.outbound.aeat.auth.select_provider` constructs providers with
``browser_session_factory=None`` by default.

This module closes that gap by providing:

* :class:`DefaultBrowserSession` — a ``BrowserSessionLike`` wrapper
  that owns a ``Playwright`` instance + :class:`BrowserSession`
  pair. Its ``close()`` tears down both.
* :func:`default_browser_session_factory` — the async callable that
  matches :class:`aeat.adapters.outbound.aeat.auth.BrowserSessionFactory` and yields a
  ``DefaultBrowserSession`` on demand.

The CLI wires this factory into ``select_provider`` so
``aeat auth login`` just works in production, while tests keep
injecting their own in-process implementations.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .....core.logging import get_logger
from .profile import Profile
from .session import BrowserSession

if TYPE_CHECKING:
    from playwright.async_api import Playwright

    from .....core.config import Settings
    from ..auth import BrowserContextLike


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
    ) -> BrowserContextLike:
        return await self._session.create_context(
            provisioner=provisioner,
            storage_state_path=storage_state_path,
        )

    async def close(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            try:
                await self._session.close()
            finally:
                try:
                    await self._playwright.stop()
                except Exception as exc:
                    logger.warning("DefaultBrowserSession: playwright stop failed: %s", exc)
                self._closed = True


async def default_browser_session_factory(settings: Settings) -> DefaultBrowserSession:
    """Start Playwright and return a wrapped :class:`BrowserSession`.

    The returned object satisfies
    :class:`aeat.adapters.outbound.aeat.auth.BrowserSessionLike` and owns its Playwright
    instance for the full lifetime. Call ``await session.close()``
    when you are done — auth providers already do this in their
    ``close()`` path.
    """
    from playwright.async_api import async_playwright

    playwright_manager = async_playwright()
    playwright = await playwright_manager.start()
    try:
        profile_name = settings.aeat_default_profile_name
        # Profile.storage_state_path is superseded by every auth-provider
        # passing an explicit kind-namespaced storage_state_path to
        # BrowserSession.create_context(). The value here is a fallback
        # for hypothetical future callers that do not override it; no
        # shipping provider currently relies on it.
        storage_state_path = settings.aeat_token_dir / f"{profile_name}-storage.json"
        profile = Profile(name=profile_name, storage_state_path=storage_state_path)

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
        with contextlib.suppress(Exception):
            await playwright.stop()
        raise


__all__ = ["DefaultBrowserSession", "default_browser_session_factory"]
