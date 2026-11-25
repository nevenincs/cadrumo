"""The one door to Playwright API requests for automated AEAT flows.

``BrowserContext.request`` and ``Page.request`` neither fire the context's
``request`` event nor pass through ``context.route``, so nothing at the browser
boundary can see or stop them. Each request therefore answers here, before it
is sent, to the remote-state guard: it goes out only when a member of the
caller's declared policy set allows it, and an empty set refuses everything.

Redirects are followed by the Playwright driver after this decision, and only
the first URL of a chain is evaluated.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from pydantic import AnyUrl

from .....core.logging import get_logger
from .....domain.calculations.registry.errors import RegistryValidationError
from .....domain.calculations.registry.remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    evaluate_remote_operation,
)

if TYPE_CHECKING:
    from playwright.async_api import APIResponse, BrowserContext

logger = get_logger(__name__)


class GuardedApiRequests:
    """Send API requests from one browser context under a declared policy set."""

    def __init__(self, context: BrowserContext, policies: Iterable[RemoteStateGuardPolicy]) -> None:
        """Bind the context whose API requests are sent and the policies that may allow them."""
        self._context = context
        self._policies = tuple(policies)

    async def get(self, url: str) -> APIResponse:
        """Send a GET the policy set allows, else raise ``RegistryValidationError`` without sending."""
        self._require_allowed("GET", url)
        return await self._context.request.get(url)

    async def post(self, url: str, *, form: Mapping[str, str]) -> APIResponse:
        """Send a form POST the policy set allows, else raise ``RegistryValidationError`` without sending."""
        self._require_allowed("POST", url)
        return await self._context.request.post(url, form=dict(form))

    def _require_allowed(self, method: str, url: str) -> None:
        if self._is_allowed(method, url):
            return
        policy_ids = tuple(policy.id for policy in self._policies)
        host, path = _redacted_target(url)
        logger.warning("aeat api request refused policies=%s method=%s host=%s path=%s", policy_ids, method, host, path)
        # The guard's own reason can quote the whole URL, query string included.
        raise RegistryValidationError(f"AEAT API request refused under policies {policy_ids!r}")

    def _is_allowed(self, method: str, url: str) -> bool:
        try:
            operation = RemoteOperation(kind="http", method=method, url=AnyUrl(url))
        except (ValueError, RegistryValidationError):
            return False
        return any(evaluate_remote_operation(policy, operation).decision == "allowed" for policy in self._policies)


def _redacted_target(url: str) -> tuple[str, str]:
    """Return only the host and path a refusal may log; an unreadable URL yields neither."""
    try:
        parts = urlsplit(url)
        return parts.hostname or "", parts.path
    except ValueError:
        return "", ""
