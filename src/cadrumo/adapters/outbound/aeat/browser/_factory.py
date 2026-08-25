"""Default Playwright browser-session factory for auth providers.

Auth providers accept a
:class:`adapters.outbound.aeat.auth.BrowserSessionFactory`: an async
callable that returns a
:class:`adapters.outbound.aeat.auth.BrowserSessionLike`. The default
factory supplies that protocol with a Playwright-backed :class:`BrowserSession`,
while :func:`adapters.outbound.aeat.auth.select_provider` still accepts
``browser_session_factory=None`` so tests and callers can inject their own
in-process implementations.

This module provides:

* :class:`DefaultBrowserSession`, the
  :class:`~adapters.outbound.aeat.auth.BrowserSessionLike` wrapper that
  owns a ``Playwright`` runtime and :class:`BrowserSession` pair.
* :func:`default_browser_session_factory`, the production
  :class:`~adapters.outbound.aeat.auth.BrowserSessionFactory` entry point
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
from typing import TYPE_CHECKING, Any, Final

from .....core import NoRecoveryOutcome
from .....core.async_cleanup import (
    close_async_resources,
)
from .....core.logging import get_logger
from ._errors import BrowserError, BrowserFailureMode, BrowserPreconditionCondition, browser_no_action_verdict
from .profile import Profile
from .session import BrowserSession

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright, Response

    from .....core.config import Settings


logger = get_logger(__name__)

_DIAGNOSTIC_PROFILE_BUCKET_ID: Final = "diagnostic-probe"
_PLAYWRIGHT_RUNTIME_LABEL: Final = "<playwright-runtime>"


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


class _SharedPlaywrightRuntimeOwner:
    """Retain a shared runtime until a stop attempt succeeds."""

    def __init__(self, playwright: Playwright) -> None:
        self.playwright = playwright
        self._close_lock = asyncio.Lock()
        self._stopped = False

    async def close(self) -> None:
        """Stop once, retaining the runtime for a later retry on failure."""
        async with self._close_lock:
            if self._stopped:
                return
            try:
                await self.playwright.stop()
            except Exception as exc:
                raise BrowserError(
                    "Playwright runtime stop failed",
                    failure_mode=BrowserFailureMode.PLAYWRIGHT_RUNTIME_STOP_FAILED,
                    context={"cause_type": type(exc).__name__},
                    precondition_verdict=browser_no_action_verdict(
                        condition=BrowserPreconditionCondition.RUNTIME_STOPPABLE,
                        facts={"playwright_runtime_stoppable": False},
                        outcome=NoRecoveryOutcome.SAFETY,
                    ),
                ) from exc
            self._stopped = True


class DefaultBrowserSession:
    """Concrete :class:`~adapters.outbound.aeat.auth.BrowserSessionLike`.

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
        self._session_closed = False
        self._playwright_stopped = False

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
            storage_state=storage_state,
        )

    async def navigate(self, page: Page, url: str) -> Response | None:
        """Navigate through :meth:`BrowserSession.navigate`."""
        return await self._session.navigate(page, url)

    async def close(self) -> None:
        """Close the session and stop the Playwright runtime.

        Idempotent after both resources close. ``BrowserSession.close()`` runs
        first, then ``Playwright.stop()``. Each successful teardown is recorded
        independently so a later call retries only the resource whose previous
        close failed.
        """
        async with self._close_lock:
            if self._session_closed and self._playwright_stopped:
                return
            session_error = await self._close_browser_session()
            stop_error = await self._stop_playwright_runtime()
            if session_error is not None:
                if stop_error is not None:
                    session_error.add_note(
                        "Playwright runtime teardown also failed "
                        f"({type(stop_error).__name__}); the runtime remains retained for retry"
                    )
                raise session_error
            if stop_error is not None:
                raise stop_error

    async def _close_browser_session(self) -> BaseException | None:
        """Close the browser session once, recording success; return the error if it raised."""
        if self._session_closed:
            return None
        try:
            await self._session.close()
        except BaseException as exc:
            return exc
        self._session_closed = True
        return None

    async def _stop_playwright_runtime(self) -> Exception | None:
        """Stop the Playwright runtime once, recording success; return the error if it raised."""
        if self._playwright_stopped:
            return None
        try:
            await self._playwright.stop()
        except Exception as exc:  # Playwright stop() exception surface is undocumented
            _log_teardown_failure(
                message="default_browser_session: playwright stop failed",
                resource=_PLAYWRIGHT_RUNTIME_LABEL,
                exc=exc,
                warning=True,
            )
            return BrowserError(
                "Playwright runtime stop failed",
                failure_mode=BrowserFailureMode.PLAYWRIGHT_RUNTIME_STOP_FAILED,
                context={"cause_type": type(exc).__name__},
                precondition_verdict=browser_no_action_verdict(
                    condition=BrowserPreconditionCondition.RUNTIME_STOPPABLE,
                    facts={"playwright_runtime_stoppable": False},
                    outcome=NoRecoveryOutcome.SAFETY,
                ),
            )
        self._playwright_stopped = True
        # A stopped Playwright runtime has reaped every browser it
        # owns even when Browser.close() raised first.
        self._session_closed = True
        return None


async def default_browser_session_factory(settings: Settings) -> DefaultBrowserSession:
    """Start Playwright and return a wrapped :class:`DefaultBrowserSession`.

    The returned object satisfies
    :class:`adapters.outbound.aeat.auth.BrowserSessionLike` and owns its
    Playwright runtime for the full lifetime. The :class:`Profile` name follows
    the active bucket when one exists and falls back to a diagnostic sentinel so
    browser connectivity probes can run before profile setup is complete.

    Auth providers pass kind-namespaced encrypted storage state explicitly to
    :meth:`BrowserSession.create_context`; the profile path is never loaded
    implicitly. Call ``await session.close()`` when you are done. Auth providers
    already do that in their ``close()`` path.
    """
    from .....core.bucket_pointer import resolve_active_bucket_id

    # This factory is reachable from the diagnostic browser-connectivity
    # probe under `aeat config status`, so a missing active profile MUST
    # NOT raise here: the probe is exactly what an operator runs to
    # diagnose a missing-profile condition. The sentinel label keeps
    # the Profile model satisfied without pretending to be a real
    # profile.
    bucket_id = resolve_active_bucket_id() or _DIAGNOSTIC_PROFILE_BUCKET_ID
    profile = Profile(name=bucket_id)
    return await create_browser_session(settings, profile)


async def create_browser_session(settings: Settings, profile: Profile) -> DefaultBrowserSession:
    """Start Playwright and return a :class:`DefaultBrowserSession`.

    Wraps a :class:`BrowserSession` for ``profile`` after the optional
    ``browser`` extra has been checked by ``_start_playwright``. If wrapper
    construction fails after Playwright starts, the partially opened runtime is
    stopped before the original failure is re-raised.
    """
    playwright = await _start_playwright()
    runtime_owner = _SharedPlaywrightRuntimeOwner(playwright)
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
        await close_async_resources(
            runtime_owner,
            task_name="cadrumo-browser-factory-error-close",
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
    owner = _SharedPlaywrightRuntimeOwner(await _start_playwright())
    try:
        yield owner.playwright
    finally:
        await close_async_resources(
            owner,
            task_name="cadrumo-shared-playwright-stop",
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
    storage_state: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[Page, BrowserContext]]:
    """Yield a :class:`BrowserSession` page/context pair and close both.

    The helper builds a short-lived :class:`BrowserSession` around the supplied
    Playwright runtime, forwards ``provisioner`` and storage-state arguments to
    :meth:`BrowserSession.create_context`, yields the fresh ``(page, context)``
    pair, and closes the context and browser session during teardown.
    """
    browser_session = BrowserSession(playwright=playwright, settings=settings, profile=profile)
    context: BrowserContext | None = None
    try:
        context = await browser_session.create_context(
            provisioner=provisioner,
            storage_state=storage_state,
        )
        page = await context.new_page()
        yield page, context
    finally:
        await close_async_resources(
            context,
            browser_session,
            task_name="cadrumo-opened-browser-page-close",
        )


async def _start_playwright() -> Playwright:
    """Start the single browser-base Playwright runtime.

    The single runtime chokepoint every browser session funnels through. Guard
    the optional ``browser`` extra here so a missing playwright is a typed
    :class:`BrowserError`, not a raw ``ModuleNotFoundError`` from the import below.
    """
    from .....core import BROWSER_EXTRA, MissingOptionalExtraError, require_optional_extra

    try:
        require_optional_extra(BROWSER_EXTRA)
    except MissingOptionalExtraError as exc:
        raise BrowserError(
            "Browser optional extra is unavailable",
            failure_mode=BrowserFailureMode.OPTIONAL_EXTRA_UNAVAILABLE,
            precondition_verdict=browser_no_action_verdict(
                condition=BrowserPreconditionCondition.OPTIONAL_EXTRA_AVAILABLE,
                facts={"browser_extra_available": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc
    try:
        from playwright.async_api import async_playwright

        playwright_manager = async_playwright()
        return await playwright_manager.start()
    except Exception as exc:
        raise BrowserError(
            "Playwright runtime start failed",
            failure_mode=BrowserFailureMode.PLAYWRIGHT_RUNTIME_START_FAILED,
            context={"cause_type": type(exc).__name__},
            precondition_verdict=browser_no_action_verdict(
                condition=BrowserPreconditionCondition.RUNTIME_STARTABLE,
                facts={"playwright_runtime_startable": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc


__all__ = [
    "DefaultBrowserSession",
    "create_browser_session",
    "default_browser_session_factory",
    "opened_browser_page",
    "shared_playwright_runtime",
]
