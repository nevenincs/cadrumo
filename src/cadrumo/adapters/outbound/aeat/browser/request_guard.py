"""Context-wide request guard for AEAT browser contexts.

A :class:`ContextRequestGuard` holds the read-only
:class:`RemoteStateGuardPolicy` set a browser context was created with and
evaluates every routed request against their union: a request is admitted
when any member policy admits it, and an empty set refuses every request.
Each member is evaluated by the one remote-state guard,
:func:`evaluate_remote_operation`, so the token scan, the host allow-lists
and the method rules are never restated here. There is no bypass, observe
mode or per-call override.

:func:`install_request_guard` routes every request of a context through the
guard. A refused request is aborted before it leaves the browser, logged
with its method, host and policy ids only, and reported to the caller's
refusal sink. An admitted request falls back to the handlers registered
before the guard and then to the network, so the guard must be the last
route registered on its context. Routes registered later on the context or
on one of its pages run before it, and the owner of a guarded context
registers none.

Playwright does not route the hop of a redirect. The guard therefore also
evaluates every redirect hop when the browser reports it. Such a hop has
already been sent, so it cannot be aborted; it is logged and reported as a
refusal with ``redirect`` set, and the owner stops the page that follows it.

The operator-view policy, :func:`operator_view_policy`, is the read-only
policy of the person-driven Sede view. :func:`operator_view_request_guard`
composes it with the configured provider's auth policy, which is the union
the view's context is created with.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Protocol
from urllib.parse import urlsplit

from .....core.logging import get_logger
from .....core.remote_authority import aeat_origin_hosts, sanctioned_gov_idp_host_suffixes
from .....domain.calculations.registry.errors import RegistryValidationError
from .....domain.calculations.registry.remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    evaluate_remote_operation,
)
from .....domain.calculations.registry.schema_base import EvidenceTier
from .._playwright import PlaywrightError

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Request, Route

logger = get_logger(__name__)

#: Policy id of the person-driven Sede view's read-only policy.
OPERATOR_VIEW_POLICY_ID: Final[str] = "aeat-operator-sede-view"

#: Chromium's error code for a request the client refused.
_ABORT_ERROR_CODE: Final[str] = "blockedbyclient"

#: URL schemes an external-browser offer may carry.
_OFFERABLE_SCHEMES: Final[frozenset[str]] = frozenset({"https", "http"})


@dataclass(frozen=True, slots=True)
class RequestGuardVerdict:
    """Decision of a :class:`ContextRequestGuard` on one request.

    ``policy_id`` names the member policy that admitted the request and is
    ``None`` for a refusal.
    """

    allowed: bool
    policy_id: str | None


class ContextRequestGuard:
    """Union of the read-only policies one browser context was created with."""

    def __init__(self, policies: Iterable[RemoteStateGuardPolicy]) -> None:
        """Hold ``policies`` as the context's member set; an empty set refuses every request."""
        self._policies = tuple(policies)

    @property
    def policies(self) -> tuple[RemoteStateGuardPolicy, ...]:
        """The member policies, in the order they are evaluated."""
        return self._policies

    @property
    def policy_ids(self) -> tuple[str, ...]:
        """The member policy ids, safe to log."""
        return tuple(policy.id for policy in self._policies)

    def evaluate(self, method: str, url: str) -> RequestGuardVerdict:
        """Return whether any member policy admits an HTTP ``method`` request to ``url``.

        A URL the guard's operation model cannot represent is refused, as is
        every request when the member set is empty.
        """
        if not self._policies:
            return RequestGuardVerdict(allowed=False, policy_id=None)
        try:
            operation = RemoteOperation(kind="http", method=method.upper(), url=url)
        except (ValueError, RegistryValidationError):
            return RequestGuardVerdict(allowed=False, policy_id=None)
        for policy in self._policies:
            if evaluate_remote_operation(policy, operation).decision == "allowed":
                return RequestGuardVerdict(allowed=True, policy_id=policy.id)
        return RequestGuardVerdict(allowed=False, policy_id=None)


def operator_view_policy() -> RemoteStateGuardPolicy:
    """Build the read-only policy of the person-driven Sede view.

    It admits the exact AEAT origins of ``[aeat.domains]`` and the Cl@ve
    identity-provider apex, GET and HEAD on any path of those hosts, and no
    POST: a POST is admitted only as an exact declared read request once that
    request is grounded, and none is grounded for the view. The whole-URL
    forbidden-token scan applies to every request, as on every policy.
    """
    idp_suffixes = sanctioned_gov_idp_host_suffixes()
    return RemoteStateGuardPolicy(
        id=OPERATOR_VIEW_POLICY_ID,
        evidence_tier=EvidenceTier.OFFICIAL_SOURCE_GUIDANCE,
        classification="authenticated_read_surface",
        allowed_hosts=aeat_origin_hosts(),
        allowed_host_suffixes=idp_suffixes,
        allows_gov_idp_hosts=True,
        allowed_read_post_paths=(),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )


def operator_view_request_guard(provider_policy: RemoteStateGuardPolicy | None) -> ContextRequestGuard:
    """Return the view context's guard: the operator-view policy plus the provider's auth policy.

    A provider without a browser auth policy, such as certificate login,
    passes ``None`` and the view admits only what the operator-view policy
    admits.
    """
    members = [operator_view_policy()]
    if provider_policy is not None:
        members.append(provider_policy)
    return ContextRequestGuard(members)


@dataclass(frozen=True, slots=True)
class RequestRefusal:
    """One request the guard refused, as reported to the refusal sink.

    ``url`` is private taxpayer data: it lives in memory only and is never
    logged, persisted or journaled by a sink. ``page`` is the page whose
    frame issued the request, when Playwright can name one. ``redirect`` is
    set for a redirect hop, which was already sent when it was refused.
    """

    method: str
    url: str
    navigation: bool
    main_frame: bool
    redirect: bool
    page: Page | None


type RefusalSink = Callable[[RequestRefusal], None]


async def install_request_guard(
    context: BrowserContext,
    guard: ContextRequestGuard,
    *,
    on_refusal: RefusalSink | None = None,
) -> None:
    """Route every request of ``context`` through ``guard``.

    Call this after every other route of the context is registered and
    before any page exists, so the guard runs first on every request the
    context's pages issue. A refused request is aborted; an admitted one
    falls back to earlier handlers and then to the network. Any failure while
    deciding refuses the request.
    """

    async def guard_route(route: Route) -> None:
        request = route.request
        try:
            verdict = guard.evaluate(request.method, request.url)
        except Exception as exc:
            logger.error(
                "aeat browser request guard failed closed exc_type=%s policies=%s",
                type(exc).__name__,
                ",".join(guard.policy_ids),
            )
            verdict = RequestGuardVerdict(allowed=False, policy_id=None)
        if verdict.allowed:
            await route.fallback()
            return
        await route.abort(_ABORT_ERROR_CODE)
        _report_refusal(guard, request, redirect=False, on_refusal=on_refusal)

    def observe_request(request: Request) -> None:
        if request.redirected_from is None:
            return
        if guard.evaluate(request.method, request.url).allowed:
            return
        _report_refusal(guard, request, redirect=True, on_refusal=on_refusal)

    await context.route("**/*", guard_route)
    context.on("request", observe_request)


def _report_refusal(
    guard: ContextRequestGuard,
    request: Request,
    *,
    redirect: bool,
    on_refusal: RefusalSink | None,
) -> None:
    """Log one refusal with redaction and hand it to the sink."""
    navigation = request.is_navigation_request()
    page, main_frame = _request_page(request)
    logger.warning(
        "aeat browser request refused method=%s host=%s navigation=%s redirect=%s policies=%s",
        request.method,
        log_safe_host(request.url),
        navigation,
        redirect,
        ",".join(guard.policy_ids),
    )
    if on_refusal is None:
        return
    refusal = RequestRefusal(
        method=request.method,
        url=request.url,
        navigation=navigation,
        main_frame=main_frame,
        redirect=redirect,
        page=page,
    )
    try:
        on_refusal(refusal)
    except Exception as exc:
        logger.error("aeat browser refusal sink failed exc_type=%s", type(exc).__name__)


def _request_page(request: Request) -> tuple[Page | None, bool]:
    """Return the page that issued ``request`` and whether its main frame did."""
    try:
        frame = request.frame
    except PlaywrightError:
        # A service-worker request has no frame.
        return None, False
    return frame.page, frame.parent_frame is None


def log_safe_host(url: str) -> str:
    """Return only the host of ``url``, the one URL part a refusal log may carry, or ``-``."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return "-"
    return host or "-"


def offerable_url(url: str) -> str | None:
    """Return ``url`` when it may be offered to the external browser, else ``None``.

    Only an absolute HTTP or HTTPS URL with a host is offered; the host's
    external-open admission revalidates it before anything opens.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme.lower() not in _OFFERABLE_SCHEMES or parts.hostname is None or parts.hostname == "":
        return None
    return url


class ViewNoticeCode(StrEnum):
    """Closed codes of the notices the Sede view reports to the person's panel."""

    REQUEST_REFUSED = "request_refused"
    """A subresource, frame, redirect hop or WebSocket request was refused."""

    NAVIGATION_REFUSED = "navigation_refused"
    """A top-level navigation of a view page was refused; offered externally."""

    POPUP_REFUSED = "popup_refused"
    """A page tried to open a popup, which was closed; offered externally."""

    DOWNLOAD_REFUSED = "download_refused"
    """A download started and was not saved; offered externally."""

    FILE_CHOOSER_REFUSED = "file_chooser_refused"
    """A page asked for a file; nothing was chosen; the page is offered externally."""


@dataclass(frozen=True, slots=True)
class ViewNotice:
    """One notice for the person's panel.

    ``offer_url`` is set where the notice offers the external browser. It is
    private taxpayer data: it lives in memory only and is handed to the
    host's external-open admission; it is never logged, persisted,
    journaled or put in a projection or result.
    """

    code: ViewNoticeCode
    offer_url: str | None = None


class ViewPageObserver(Protocol):
    """Page-observer hook of a Sede view context.

    The browser session calls it on the event loop that drives the context.
    Both methods must return promptly and must not raise; a raised exception
    is logged by type and does not change any guard decision.
    """

    def page_opened(self, page: Page) -> None:
        """Expose a page opened in the view context by code, never a popup.

        The screencast attaches to the page reported here. Provider login
        pages reach the screencast through this call.
        """
        ...

    def notice(self, notice: ViewNotice) -> None:
        """Report a refusal, popup, download or file chooser to the panel."""
        ...


__all__ = [
    "OPERATOR_VIEW_POLICY_ID",
    "ContextRequestGuard",
    "RefusalSink",
    "RequestGuardVerdict",
    "RequestRefusal",
    "ViewNotice",
    "ViewNoticeCode",
    "ViewPageObserver",
    "install_request_guard",
    "log_safe_host",
    "offerable_url",
    "operator_view_policy",
    "operator_view_request_guard",
]
