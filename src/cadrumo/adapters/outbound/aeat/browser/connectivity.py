"""Synchronous AEAT browser-connectivity probe owned by the outbound adapter.

The probe opens the production browser session, navigates to the configured
AEAT Sede target, and returns the concrete
:class:`adapters.outbound.aeat.browser.site_health_records.SiteHealthStatus` record
produced by the browser navigation boundary. Browser session creation,
navigation, status construction, and teardown stay together here so the
application layer does not become a transport or site-health owner.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .....core.async_cleanup import close_async_resources
from .....core.errors.hierarchy import SiteHealthError, SiteHealthState
from .....core.time.clock import now
from .....core.url_validation import ANY_HTTP_URL_ADAPTER
from .errors import BrowserValidationError
from .factory import default_browser_session_factory
from .site_health_records import SiteHealthEvidence, SiteHealthStatus

if TYPE_CHECKING:
    from .....core.config import Settings


def probe_browser_connectivity(settings: Settings | None = None) -> SiteHealthStatus:
    """Probe the configured AEAT browser target through the browser adapter.

    ``load_settings()`` is resolved only when a caller does not provide an
    explicit settings object, preserving the active settings override context.
    """
    if settings is None:
        from .....core.config import load_settings

        settings = load_settings()
    return asyncio.run(_probe_browser_connectivity(settings))


async def _probe_browser_connectivity(settings: Settings) -> SiteHealthStatus:
    """Run one browser session and return its site-health classification."""
    url = settings.site_health_probe_url
    session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await session.create_context()
        page = await context.new_page()
        try:
            await session.navigate(page, url)
        except SiteHealthError as exc:
            status = exc.status
            if not isinstance(status, SiteHealthStatus):
                raise BrowserValidationError("SiteHealthError carried a non-SiteHealthStatus payload") from exc
            return status
        return _ok_site_health_status(url)
    finally:
        await close_async_resources(
            context,
            session,
            task_name="cadrumo-browser-connectivity-close",
        )


def _ok_site_health_status(url: str) -> SiteHealthStatus:
    """Build the canonical healthy status after successful navigation."""
    return SiteHealthStatus(
        state=SiteHealthState.OK,
        evidence=SiteHealthEvidence(
            url=ANY_HTTP_URL_ADAPTER.validate_python(url),
            http_status=200,
            html_fragment="",
            detected_markers=("healthy",),
        ),
        observed_at=now(),
    )


__all__ = ["probe_browser_connectivity"]
