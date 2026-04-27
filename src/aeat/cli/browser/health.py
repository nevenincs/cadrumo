"""``aeat browser health`` command implementation (#95).

Runs a single navigation probe against
:attr:`aeat.config.Settings.site_health_probe_url` and prints either a
human-readable summary or the JSON-serialised
:class:`aeat.browser._site_health.SiteHealthStatus`. Exit codes follow
the table locked into [[2026-04-13-aeat-mantenimiento-detection-adr]]:

- ``0`` — :attr:`aeat.browser._site_health.SiteHealthState.OK`
- ``2`` — :attr:`aeat.browser._site_health.SiteHealthState.MANTENIMIENTO`
- ``3`` — :attr:`aeat.browser._site_health.SiteHealthState.WAF_CHALLENGE`
- ``4`` — :attr:`aeat.browser._site_health.SiteHealthState.RATE_LIMITED`
- ``5`` — :attr:`aeat.browser._site_health.SiteHealthState.UNREACHABLE`
- ``6`` — :attr:`aeat.browser._site_health.SiteHealthState.UNKNOWN_ERROR`

Typer reserves exit code ``1`` for usage errors (unchanged).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime
from typing import Any, Protocol

import typer

from ...browser._site_health import (
    _URL_ADAPTER,
    SiteHealthEvidence,
    SiteHealthState,
    SiteHealthStatus,
)
from ...config import Settings
from ...errors import SiteHealthError
from ...logging import get_logger
from .._errors import json_output_requested
from .._schemas import OutputRootSchema, emit_json_success, register_schema

logger = get_logger(__name__)


@register_schema("browser health")
class BrowserHealthJson(OutputRootSchema[SiteHealthStatus]):
    """Schema for ``aeat browser health --json``."""


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


class _RealProbe:
    """Navigation probe that always releases Playwright on exit.

    Extracted to module scope so the cleanup contract (``playwright.stop()``
    always runs; ``context.close()`` runs when a context was acquired)
    can be exercised by concrete unit tests without a real Playwright
    driver. The ``session`` argument only needs to satisfy the two
    methods used below: ``create_context`` and ``navigate``.
    """

    def __init__(self, session: Any, playwright: Any) -> None:
        self._session = session
        self._playwright = playwright

    async def probe(self, url: str) -> None:
        context: Any = None
        try:
            context = await self._session.create_context()
            page = await context.new_page()
            await self._session.navigate(page, url)
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    logger.exception("browser_health: context.close() failed")
            try:
                await self._session.close()
            except Exception:
                logger.exception("browser_health: session.close() failed")
            await self._playwright.stop()


async def _default_probe_factory(settings: Settings) -> HealthProbeLike:
    """Build the production probe backed by a real ``BrowserSession``.

    Imported lazily so test doubles can replace :data:`PROBE_FACTORY`
    without paying the cost of a Playwright import.
    """
    from playwright.async_api import async_playwright

    from ...browser.profile import Profile
    from ...browser.session import BrowserSession

    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-storage.json",
    )
    playwright = await async_playwright().start()
    session = BrowserSession(
        playwright=playwright,
        settings=settings,
        profile=profile,
    )
    return _RealProbe(session=session, playwright=playwright)


PROBE_FACTORY = _default_probe_factory
"""Module-level factory callable that the CLI uses to build its probe.

Tests replace this attribute with a concrete async factory that
returns a :class:`HealthProbeLike` double built from a real fixture.
Replacing the factory is the project-sanctioned dependency-injection
seam for the CLI; no ``unittest.mock`` is required.
"""

ProbeFactory = Callable[[Settings], Awaitable[HealthProbeLike]]
_OVERRIDE_PROBE_FACTORY: ProbeFactory | None = None


def install_probe_factory(factory: ProbeFactory | None) -> None:
    """Install an explicit probe factory override for the CLI."""

    global _OVERRIDE_PROBE_FACTORY
    _OVERRIDE_PROBE_FACTORY = factory


@contextlib.contextmanager
def override_probe_factory(factory: ProbeFactory) -> Iterator[None]:
    """Temporarily override the CLI probe factory."""

    install_probe_factory(factory)
    try:
        yield
    finally:
        install_probe_factory(None)


def _resolve_probe_factory() -> ProbeFactory:
    if _OVERRIDE_PROBE_FACTORY is not None:
        return _OVERRIDE_PROBE_FACTORY
    return PROBE_FACTORY


def _render_human(status: SiteHealthStatus) -> str:
    """Render a one-paragraph human summary for console output."""
    retry = ""
    if status.retry_after_seconds is not None:
        retry = f" retry_after_seconds={status.retry_after_seconds}"
    markers = ", ".join(status.evidence.detected_markers) or "(none)"
    return f"state={status.state.value} http_status={status.evidence.http_status}{retry} markers=[{markers}]"


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
        probe = await _resolve_probe_factory()(settings)
        try:
            await probe.probe(url)
        except SiteHealthError as exc:
            return exc.status
        return _build_ok_status(url)

    status = asyncio.run(_run())
    if json_output or json_output_requested():
        emit_json_success("browser health", status, sort_keys=True)
    else:
        typer.echo(_render_human(status))
    raise typer.Exit(code=_EXIT_CODES[status.state])
