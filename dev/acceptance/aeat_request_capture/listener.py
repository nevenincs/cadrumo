"""Attach a request recorder to every Playwright context a process opens.

The product exposes no hook for this and must not gain one, so the listener wraps
Playwright's own classes for the length of a capture and restores them afterwards.
It reads a request's method and URL and nothing else: headers, bodies and cookies
are never touched. The one thing it stops is a request for a notification's detail
page, because opening an unread notification serves it legally.

``BrowserContext.request`` and ``Page.request`` fire no context event, so API
requests are observed by wrapping their client. Requests a service worker makes
itself fire no context event either; a worker's registration is counted so the
gap is visible in the report.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Generator
from contextlib import contextmanager
from typing import Any, Final
from urllib.parse import urlsplit

from playwright.async_api import (
    APIRequestContext,
    Browser,
    BrowserContext,
    BrowserType,
    Page,
    Request,
    Route,
    WebSocket,
    Worker,
)

from .recorder import CaptureRecorder

BROWSER_SOURCE: Final = "browser"
API_SOURCE: Final = "api"
WEBSOCKET_METHOD: Final = "WEBSOCKET"
SERVICE_WORKER_METHOD: Final = "SERVICEWORKER"
_API_VERBS: Final = ("delete", "get", "head", "patch", "post", "put")

type _AsyncMethod = Callable[..., Coroutine[Any, Any, Any]]


class NotificationDetailRefusedError(RuntimeError):
    """A capture reached for a notification's detail page and was stopped before sending."""


class RequestListener:
    """Feed one recorder from the contexts and API clients of this process."""

    def __init__(self, recorder: CaptureRecorder, *, notification_detail_paths: tuple[str, ...] = ()) -> None:
        """Bind the recorder and the detail paths the capture stops."""
        self._recorder = recorder
        self._detail_paths = notification_detail_paths

    async def attach_context(self, context: BrowserContext) -> None:
        """Observe ``context`` and every page it opens, before any of them navigates."""
        context.on("request", self._on_request)
        context.on("page", self._watch_page)
        context.on("serviceworker", self._on_service_worker)
        for page in context.pages:
            self._watch_page(page)
        for path in self._detail_paths:
            await context.route(f"**{path}*", _abort_notification_detail)

    def observe_api_request(self, method: str, url: str) -> None:
        """Record one API request and stop it when it targets a notification's detail page."""
        self._recorder.observe(API_SOURCE, method, url)
        if self._recorder.is_notification_detail(url):
            raise NotificationDetailRefusedError("Capture refused an API request for a notification detail page")

    def _on_request(self, request: Request) -> None:
        self._recorder.observe(BROWSER_SOURCE, request.method, request.url)

    def _watch_page(self, page: Page) -> None:
        page.on("websocket", self._on_websocket)

    def _on_websocket(self, websocket: WebSocket) -> None:
        self._recorder.observe(BROWSER_SOURCE, WEBSOCKET_METHOD, websocket.url)

    def _on_service_worker(self, worker: Worker) -> None:
        self._recorder.observe(BROWSER_SOURCE, SERVICE_WORKER_METHOD, worker.url)


async def _abort_notification_detail(route: Route) -> None:
    await route.abort()


def _attaching_context(original: _AsyncMethod, listener: RequestListener) -> _AsyncMethod:
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        context = await original(*args, **kwargs)
        await listener.attach_context(context)
        return context

    return wrapped


def _observing_verb(original: _AsyncMethod, method: str, listener: RequestListener) -> _AsyncMethod:
    async def wrapped(client: APIRequestContext, url: str, *args: Any, **kwargs: Any) -> Any:
        listener.observe_api_request(method, url)
        return await original(client, url, *args, **kwargs)

    return wrapped


def _observing_fetch(original: _AsyncMethod, listener: RequestListener) -> _AsyncMethod:
    async def wrapped(client: APIRequestContext, target: str | Request, *args: Any, **kwargs: Any) -> Any:
        if isinstance(target, str):
            listener.observe_api_request(kwargs.get("method") or "GET", target)
        else:
            listener.observe_api_request(kwargs.get("method") or target.method, target.url)
        return await original(client, target, *args, **kwargs)

    return wrapped


@contextmanager
def observing_playwright(listener: RequestListener) -> Generator[None]:
    """Wrap Playwright so every context and API request of this process reaches ``listener``."""
    replacements: list[tuple[type, str, _AsyncMethod]] = [
        (Browser, "new_context", _attaching_context(Browser.new_context, listener)),
        (BrowserType, "launch_persistent_context", _attaching_context(BrowserType.launch_persistent_context, listener)),
        (APIRequestContext, "fetch", _observing_fetch(APIRequestContext.fetch, listener)),
    ]
    for verb in _API_VERBS:
        replacements.append(
            (APIRequestContext, verb, _observing_verb(getattr(APIRequestContext, verb), verb.upper(), listener))
        )
    originals = [(owner, name, vars(owner)[name]) for owner, name, _replacement in replacements]
    for owner, name, replacement in replacements:
        setattr(owner, name, replacement)
    try:
        yield
    finally:
        for owner, name, original in originals:
            setattr(owner, name, original)


def notification_detail_path(detail_route: str) -> str:
    """Return the bare path of the configured notification detail route."""
    return urlsplit(detail_route).path
