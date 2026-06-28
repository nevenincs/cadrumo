"""Default Playwright browser-session factory for auth providers.

Auth providers accept a
:class:`aeat.adapters.outbound.aeat.auth.BrowserSessionFactory`: an async
callable that returns a
:class:`aeat.adapters.outbound.aeat.auth.BrowserSessionLike`. The default
factory supplies that protocol with a Playwright-backed :class:`BrowserSession`,
while :func:`aeat.adapters.outbound.aeat.auth.select_provider` still accepts
``browser_session_factory=None`` so tests and callers can inject their own
in-process implementations.

This module provides:

* :class:`DefaultBrowserSession`, the
  :class:`~aeat.adapters.outbound.aeat.auth.BrowserSessionLike` wrapper that
  owns a ``Playwright`` runtime and :class:`BrowserSession` pair.
* :func:`default_browser_session_factory`, the production
  :class:`~aeat.adapters.outbound.aeat.auth.BrowserSessionFactory` entry point
  used by auth providers and diagnostics.
* :func:`shared_playwright_runtime` and :func:`opened_browser_page`, the
  lower-level helpers used by bulk Sede readers that need to reuse one
  Playwright runtime across several :class:`Profile`-scoped contexts.

The factory path owns Playwright startup, optional ``browser`` extra checks, and
best-effort teardown logging. Auth providers remain typed to the protocol, while
this module carries the concrete runtime wiring.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from .....core.logging import get_logger
from .profile import Profile
from .session import BrowserSession

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright, Response

    from .....core.config import Settings


logger = get_logger(__name__)

_DIAGNOSTIC_PROFILE_BUCKET_ID: Final = "diagnostic-probe"
_PLAYWRIGHT_RUNTIME_LABEL: Final = "<playwright-runtime>"
_BROWSER_CONTEXT_LABEL: Final = "<browser-context>"


def _log_teardown_failure(
    *,
    message: str,
    resource: str,
    exc: BaseException,
    warning: bool = False,
) -> None:
    """Log teardown degradation without serialising exception payloads."""
    log = logger.warning if warning else logger.debug
    log("%s resource=%s failure=%s", message, resource, type(exc).__name__)


class DefaultBrowserSession:
    """Concrete :class:`~aeat.adapters.outbound.aeat.auth.BrowserSessionLike`.

    Auth providers depend on the protocol rather than on :class:`BrowserSession`
    or Playwright directly. ``DefaultBrowserSession`` is the production adapter
    for that protocol: it owns one Playwright runtime, one :class:`BrowserSession`,
    and a :class:`Profile` through the wrapped session. Its :meth:`close` method
    tears the pair down in order, so provider ``close()`` paths do not need a
    second runtime-specific hook.
    """

    def __init__(
        self,
        playwright: Playwright,
        session: BrowserSession,
    ) -> None:
        """Wrap an existing Playwright runtime and :class:`BrowserSession` pair.

        Args:
            playwright: An already-started Playwright runtime.  Its
                ``stop()`` is called once by :meth:`close`.
            session: A :class:`BrowserSession` built from ``playwright``.
                Its ``close()`` is called before the Playwright runtime
                is stopped.
        """
        self._playwright = playwright
        self._session = session
        self._close_lock = asyncio.Lock()
        self._closed = False

    @property
    def profile(self) -> Profile:
        """The :class:`Profile` associated with the underlying session."""
        return self._session.profile

    # ADAPTER-INTERNAL-ALIAS-RATIONALE-PLAYWRIGHT-PROVISIONER: provisioner is an
    # optional duck-typed adapter that exposes build_context_kwargs(); Playwright
    # ships no stub for the caller-defined provisioner contract.
    async def create_context(
        self,
        *,
        provisioner: Any | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> BrowserContext:
        """Delegate context creation to the underlying :class:`BrowserSession`.

        Accepts the same keyword arguments as
        :meth:`BrowserSession.create_context` and forwards them unchanged, so
        certificate provisioners and persisted Cl@ve storage state use the same
        path as callers that work with :class:`BrowserSession` directly.
        """
        return await self._session.create_context(
            provisioner=provisioner,
            storage_state_path=storage_state_path,
            storage_state=storage_state,
        )

    async def navigate(self, page: Page, url: str) -> Response | None:
        """Navigate through :meth:`BrowserSession.navigate`."""
        return await self._session.navigate(page, url)

    async def close(self) -> None:
        """Close the session and stop the Playwright runtime.

        Idempotent: subsequent calls are no-ops. ``BrowserSession.close()``
        runs first; ``Playwright.stop()`` runs in the ``finally`` block so
        Playwright resources are released even when the session teardown
        raises.
        """
        async with self._close_lock:
            if self._closed:
                return
            try:
                await self._session.close()
            finally:
                try:
                    await self._playwright.stop()
                except Exception as exc:  # Playwright stop() exception surface is undocumented; teardown must not abort
                    _log_teardown_failure(
                        message="default_browser_session: playwright stop failed",
                        resource=_PLAYWRIGHT_RUNTIME_LABEL,
                        exc=exc,
                        warning=True,
                    )
                self._closed = True


async def default_browser_session_factory(settings: Settings) -> DefaultBrowserSession:
    """Start Playwright and return a wrapped :class:`DefaultBrowserSession`.

    The returned object satisfies
    :class:`aeat.adapters.outbound.aeat.auth.BrowserSessionLike` and owns its
    Playwright runtime for the full lifetime. The :class:`Profile` name follows
    the active bucket when one exists and falls back to a diagnostic sentinel so
    browser connectivity probes can run before profile setup is complete.

    Auth providers pass their own kind-namespaced storage-state paths to
    :meth:`BrowserSession.create_context`; the profile storage path built here is
    only the fallback for direct callers. Call ``await session.close()`` when you
    are done. Auth providers already do that in their ``close()`` path.
    """
    from .....core import resolve_active_bucket_id

    # This factory is reachable from the diagnostic browser-connectivity
    # probe under `aeat config status`, so a missing active profile MUST
    # NOT raise here: the probe is exactly what an operator runs to
    # diagnose a missing-profile condition. The sentinel label keeps
    # the Profile model satisfied without pretending to be a real
    # profile.
    bucket_id = resolve_active_bucket_id() or _DIAGNOSTIC_PROFILE_BUCKET_ID
    # Profile.storage_state_path is superseded by every auth-provider
    # passing an explicit kind-namespaced storage_state_path to
    # BrowserSession.create_context(). The value here is a fallback
    # for hypothetical future callers that do not override it; no
    # shipping provider currently relies on it. The storage-state
    # filename is keyed by the active bucket UUID, consistent with the
    # other token/lock filename call sites.
    storage_state_path = settings.aeat_token_dir / f"{bucket_id}-storage.json"
    profile = Profile(name=bucket_id, storage_state_path=storage_state_path)
    return await create_browser_session(settings, profile)


async def create_browser_session(settings: Settings, profile: Profile) -> DefaultBrowserSession:
    """Start Playwright and return a :class:`DefaultBrowserSession`.

    Wraps a :class:`BrowserSession` for ``profile`` after the optional
    ``browser`` extra has been checked by ``_start_playwright``. If wrapper
    construction fails after Playwright starts, the partially opened runtime is
    stopped before the original failure is re-raised.
    """
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
            _log_teardown_failure(
                message="browser factory: playwright.stop() during error teardown failed",
                resource=_PLAYWRIGHT_RUNTIME_LABEL,
                exc=stop_exc,
            )
        raise


@asynccontextmanager
async def shared_playwright_runtime() -> AsyncIterator[Playwright]:
    """Yield a centrally owned Playwright runtime for bulk browser workflows.

    Callers that need several :class:`Profile`-scoped contexts can start
    Playwright once here and pass the yielded runtime into
    :func:`opened_browser_page`. The context manager owns only the Playwright
    runtime; each page/context pair is still owned by the helper that opens it.
    """
    playwright = await _start_playwright()
    try:
        yield playwright
    finally:
        try:
            await playwright.stop()
        except Exception as stop_exc:
            _log_teardown_failure(
                message="browser factory: playwright.stop() during runtime teardown failed",
                resource=_PLAYWRIGHT_RUNTIME_LABEL,
                exc=stop_exc,
            )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-PLAYWRIGHT-PROVISIONER: provisioner is duck-
# typed and storage_state is Playwright's free-shape JSON blob.
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
    """Yield a :class:`BrowserSession` page/context pair and close both.

    The helper builds a short-lived :class:`BrowserSession` around the supplied
    Playwright runtime, forwards ``provisioner`` and storage-state arguments to
    :meth:`BrowserSession.create_context`, yields the fresh ``(page, context)``
    pair, and closes the context and browser session during teardown.
    """
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
            _log_teardown_failure(
                message="browser factory: context.close() during teardown failed",
                resource=_BROWSER_CONTEXT_LABEL,
                exc=close_exc,
            )
        await browser_session.close()


async def _start_playwright() -> Playwright:
    """Start the single browser-base Playwright runtime.

    The single runtime chokepoint every browser session funnels through. Guard
    the optional ``browser`` extra here so a missing playwright is an instructive
    :class:`BrowserError`, not a raw ``ModuleNotFoundError`` from the import below.
    """
    from .....core import BROWSER_EXTRA, MissingOptionalExtraError, require_optional_extra
    from ._errors import BrowserError

    try:
        require_optional_extra(BROWSER_EXTRA)
    except MissingOptionalExtraError as exc:
        raise BrowserError(message=str(exc), suggestion=exc.install_hint) from exc
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
