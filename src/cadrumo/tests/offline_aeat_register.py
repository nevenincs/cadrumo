"""Canonical routed-browser support for offline declarations-register proofs."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from playwright.async_api import Route, async_playwright

from ..adapters.outbound.aeat.sede.declarations import DeclaracionesRegisterSession
from ..application.auth.session_types import AeatSession, CertificateSessionDetail
from ..core.config import override_settings
from . import FIXTURES_DIR

_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"
_TOTAL_REGISTROS_RE = re.compile(r"de (\d+) en total")
_LISTITEM_RE = re.compile(r'class="[^"]*\bz-listitem\b')


def aeat_sede_fixture(stem: str) -> str:
    """Load one canonical synthetic Sede document."""
    return (_FIXTURE_ROOT / f"{stem}.html").read_text(encoding="utf-8")


def declared_register_total(html: str) -> int | None:
    """Read the total declared by a register document's own pager."""
    match = _TOTAL_REGISTROS_RE.search(html)
    return None if match is None else int(match.group(1))


def rendered_register_rows(html: str) -> int:
    """Count rows directly from synthetic register markup."""
    return len(_LISTITEM_RE.findall(html))


def offline_aeat_session() -> AeatSession:
    """Build a real certificate session carrying no persisted browser state."""
    authenticated_at = datetime(2026, 8, 8, 9, 0, tzinfo=UTC)
    return AeatSession(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + timedelta(hours=8),
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="aabbcc",
            certificate_subject="CN=test",
        ),
    )


@dataclass
class RoutedRegisterDocuments:
    """Track which deterministic documents the real browser consumed."""

    pending: list[str]
    served: list[str] = field(default_factory=list)

    async def serve(self, route: Route) -> None:
        """Fulfil every browser request locally, advancing on navigation."""
        if not route.request.is_navigation_request():
            await route.fulfill(status=204, body="")
            return
        body = self.pending.pop(0) if self.pending else self.served[-1]
        self.served.append(body)
        await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)


@asynccontextmanager
async def open_routed_declarations_register(
    documents: Sequence[str],
    *,
    ver_click_timeout_ms: int | None = None,
) -> AsyncGenerator[tuple[DeclaracionesRegisterSession, RoutedRegisterDocuments]]:
    """Open the real register session over locally routed deterministic HTML."""
    routed = RoutedRegisterDocuments(pending=list(documents))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.route("**/*", routed.serve)
            settings = {
                "cadrumo_browser_form_interaction_timeout_ms": 3000,
                "cadrumo_browser_buscar_settle_ms": 50,
            }
            if ver_click_timeout_ms is not None:
                settings["cadrumo_browser_ver_click_timeout_ms"] = ver_click_timeout_ms
            with override_settings(**settings):
                yield DeclaracionesRegisterSession(offline_aeat_session(), page, context), routed
        finally:
            await browser.close()


__all__ = [
    "RoutedRegisterDocuments",
    "aeat_sede_fixture",
    "declared_register_total",
    "offline_aeat_session",
    "open_routed_declarations_register",
    "rendered_register_rows",
]
