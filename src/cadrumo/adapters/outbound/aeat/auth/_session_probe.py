"""Shared authenticated-landing navigation probe for AEAT auth providers.

The Cl@ve Móvil and Cl@ve Permanente providers both re-probe a persisted
browser session by navigating an owned :class:`BrowserContextLike` to a
target URL and deciding whether the final landing page is an authenticated
AEAT surface. The navigation state machine — open a page, ``goto`` the probe
URL, read the status and landing URL, optionally run a provider-specific
on-landing dispatch, classify the landing, and always close the page — was
cloned near-byte-identically across both providers.

:func:`run_authenticated_landing_probe` owns that one state machine. Each
provider supplies:

* ``is_authenticated_landing`` — the provider's landing predicate.
* ``on_landing`` — an optional hook (Cl@ve Móvil uses it for the selector-page
  Cl@ve-button dispatch; Cl@ve Permanente passes ``None``).
* ``log_label`` — the operator-facing label used in the navigation-failure and
  page-close-suppression log lines.

The provider keeps its own guards, target/probe-URL resolution, and typed
:class:`AeatLoginAssertion` assembly; only the navigation probe is shared.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from .....core import STRICT_FROZEN_CONFIG
from .....core.logging import get_logger

if TYPE_CHECKING:
    from .authenticator_types import BrowserContextLike, BrowserPageLike

log = get_logger(__name__)


AuthenticatedLandingPredicate = Callable[[str, str], bool]
"""``(landing_url, target_path) -> bool`` provider landing classifier."""

OnLandingHook = Callable[["BrowserPageLike", str, str], Awaitable[bool]]
"""``(page, landing_url, target_path) -> acted`` post-landing dispatch hook.

Returning ``True`` signals the probe that the hook navigated the page, so the
probe re-reads the page's landing URL afterwards; ``False`` leaves the observed
landing URL unchanged.
"""


def _landing_is_authenticated_session(
    *,
    status_code: int,
    landing_url: str | None,
    target_path: str,
    is_authenticated_landing: AuthenticatedLandingPredicate,
) -> bool:
    """Return ``True`` when the landing is a successful authenticated AEAT page."""
    if not landing_url or not (200 <= status_code < 400):
        return False
    return is_authenticated_landing(landing_url, target_path)


class SessionProbeOutcome(BaseModel):
    """Result of a single authenticated-landing navigation probe."""

    model_config = STRICT_FROZEN_CONFIG

    status_code: int
    landing_url: str | None
    session_cookie_present: bool
    error_message: str | None
    elapsed_ms: int


async def run_authenticated_landing_probe(
    context: BrowserContextLike,
    *,
    probe_url: str,
    target_path: str,
    navigation_timeout_ms: int,
    is_authenticated_landing: AuthenticatedLandingPredicate,
    on_landing: OnLandingHook | None,
    log_label: str,
) -> SessionProbeOutcome:
    """Navigate ``context`` to ``probe_url`` and classify the landing page.

    Opens a new page on the owned ``context``, navigates to ``probe_url``, and
    reads the response status and landing URL. When ``on_landing`` is supplied
    and a landing URL is observed, the hook runs and — if it reports acting —
    the landing URL is re-read. The landing counts as an authenticated session
    only when the status is in ``[200, 400)``, a landing URL is present, and
    ``is_authenticated_landing`` accepts it. Navigation failures are captured
    into ``error_message``; the page is always closed.
    """
    start = time.perf_counter()
    status_code = 0
    landing_url: str | None = None
    session_cookie_present = False
    error_message: str | None = None
    page: BrowserPageLike | None = None
    try:
        page = await context.new_page()
        response = await page.goto(probe_url, timeout=navigation_timeout_ms)
        if response is not None:
            status_code = int(response.status)
            landing_url = getattr(page, "url", None)
            if on_landing is not None and landing_url and await on_landing(page, landing_url, target_path):
                landing_url = getattr(page, "url", None)
            session_cookie_present = _landing_is_authenticated_session(
                status_code=status_code,
                landing_url=landing_url,
                target_path=target_path,
                is_authenticated_landing=is_authenticated_landing,
            )
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        log.warning("%s: probe navigation failed for %s", log_label, probe_url, exc_info=True)
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception as _exc:
                log.debug("%s: page.close suppressed: %s", log_label, _exc, exc_info=True)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return SessionProbeOutcome(
        status_code=status_code,
        landing_url=landing_url,
        session_cookie_present=session_cookie_present,
        error_message=error_message,
        elapsed_ms=elapsed_ms,
    )
