"""``aeat browser health`` command implementation (#95).

Runs a single navigation probe against
:attr:`aeat.config.Settings.site_health_probe_url` and prints either a
human-readable summary or the JSON-serialised
:class:`aeat.status.SiteHealthStatus`. Exit codes follow the table
locked into [[2026-04-13-aeat-mantenimiento-detection-adr]]:

- ``0`` — :attr:`aeat.status.SiteHealthState.OK`
- ``2`` — :attr:`aeat.status.SiteHealthState.MANTENIMIENTO`
- ``3`` — :attr:`aeat.status.SiteHealthState.WAF_CHALLENGE`
- ``4`` — :attr:`aeat.status.SiteHealthState.RATE_LIMITED`
- ``5`` — :attr:`aeat.status.SiteHealthState.UNREACHABLE`
- ``6`` — :attr:`aeat.status.SiteHealthState.UNKNOWN_ERROR`

Typer reserves exit code ``1`` for usage errors (unchanged).
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Protocol

import typer

from aeat.config import Settings
from aeat.errors import SiteHealthError
from aeat.logging import get_logger
from aeat.status import (
    SiteHealthEvidence,
    SiteHealthState,
    SiteHealthStatus,
)
from aeat.status._site_health import _URL_ADAPTER

logger = get_logger(__name__)


_EXIT_CODES: dict[SiteHealthState, int] = {
    SiteHealthState.OK: 0,
    SiteHealthState.MANTENIMIENTO: 2,
    SiteHealthState.WAF_CHALLENGE: 3,
    SiteHealthState.RATE_LIMITED: 4,
    SiteHealthState.UNREACHABLE: 5,
    SiteHealthState.UNKNOWN_ERROR: 6,
}


class HealthProbeLike(Protocol):
    """Structural protocol for the async health probe used by the CLI.

    Concrete implementations (the real
    :class:`aeat.browser.BrowserSession` wrapper, or a test double
    built from a fixture) expose one async method that returns
    ``None`` when the probe is healthy or raises
    :class:`SiteHealthError` when the parser suite classifies the
    response as non-OK.
    """

    async def probe(self, url: str) -> None: ...


async def _default_probe_factory(settings: Settings) -> HealthProbeLike:
    """Build the production probe backed by a real ``BrowserSession``.

    Imported lazily so test doubles can replace :data:`PROBE_FACTORY`
    without paying the cost of a Playwright import.
    """
    from playwright.async_api import async_playwright

    from aeat.browser.profile import Profile
    from aeat.browser.session import BrowserSession

    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=settings.aeat_token_dir / f"{settings.aeat_default_profile_name}.json",
    )
    playwright = await async_playwright().start()
    session = BrowserSession(
        playwright=playwright,
        settings=settings,
        profile=profile,
    )

    class _RealProbe:
        async def probe(self, url: str) -> None:
            context = await session.create_context()
            page = await context.new_page()
            try:
                await session.navigate(page, url)
            finally:
                await context.close()
                await playwright.stop()

    return _RealProbe()


PROBE_FACTORY = _default_probe_factory
"""Module-level factory callable that the CLI uses to build its probe.

Tests replace this attribute with a concrete async factory that
returns a :class:`HealthProbeLike` double built from a real fixture.
Replacing the factory is the project-sanctioned dependency-injection
seam for the CLI; no ``unittest.mock`` is required.
"""


def _render_human(status: SiteHealthStatus) -> str:
    """Render a one-paragraph human summary for console output."""
    retry = ""
    if status.retry_after_seconds is not None:
        retry = f" retry_after_seconds={status.retry_after_seconds}"
    markers = ", ".join(status.evidence.detected_markers) or "(none)"
    return f"state={status.state.value} http_status={status.evidence.http_status}{retry} markers=[{markers}]"


def _render_json(status: SiteHealthStatus) -> str:
    """Render the :class:`SiteHealthStatus` as pretty JSON."""
    return json.dumps(status.model_dump(mode="json"), indent=2, sort_keys=True, default=str)


def _build_ok_status(url: str) -> SiteHealthStatus:
    """Synthesise an OK :class:`SiteHealthStatus` for a successful probe."""
    return SiteHealthStatus(
        state=SiteHealthState.OK,
        evidence=SiteHealthEvidence(
            url=_URL_ADAPTER.validate_python(url),
            http_status=200,
            html_fragment="",
            detected_markers=("healthy",),
        ),
        observed_at=datetime.now(tz=UTC),
    )


def health_cmd(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit SiteHealthStatus as JSON instead of a human summary.",
    ),
) -> None:
    """Probe the configured AEAT site-health URL once and exit.

    The command opens a real (or test-injected) browser session,
    navigates to :attr:`Settings.site_health_probe_url`, and classifies
    the response. Exit codes follow the ADR-locked table.
    """
    settings = Settings()
    url = settings.site_health_probe_url

    async def _run() -> SiteHealthStatus:
        probe = await PROBE_FACTORY(settings)
        try:
            await probe.probe(url)
        except SiteHealthError as exc:
            return exc.status
        return _build_ok_status(url)

    status = asyncio.run(_run())
    if json_output:
        typer.echo(_render_json(status))
    else:
        typer.echo(_render_human(status))
    raise typer.Exit(code=_EXIT_CODES[status.state])
