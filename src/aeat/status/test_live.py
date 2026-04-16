"""Opt-in live tests for the AEAT status reader (#43).

These tests hit the real AEAT *Sede Electrónica* through a live
Playwright browser with a real client certificate. They are
skipped by default and only run when the canonical project-wide
opt-in flag :envvar:`AEAT_LIVE_TESTS_ENABLED` is truthy and the
operator has configured the certificate settings.

No mocks, no patches, no fakes, no stubs.
"""

from __future__ import annotations

import pytest
from playwright.async_api import async_playwright

from aeat.auth import CertificateBackend, load_certificate_from_settings
from aeat.browser.profile import Profile
from aeat.browser.session import BrowserSession
from aeat.config import load_settings
from aeat.status import StatusCache, StatusReader

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


async def test_live_fetch_expedientes(tmp_path) -> None:
    """Exercise one real read-only `fetch_expedientes()` pass."""
    settings = load_settings()
    if not settings.aeat_live_tests_enabled:
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not set")
    if settings.aeat_certificate_path is None or settings.aeat_certificate_password_secret is None:
        pytest.skip("AEAT certificate env vars are not fully configured")
    if settings.aeat_certificate_backend is not CertificateBackend.PLAYWRIGHT_CONTEXT:
        pytest.skip("AEAT_CERTIFICATE_BACKEND must be PLAYWRIGHT_CONTEXT for live browser verification")

    cert = load_certificate_from_settings(settings)

    async with async_playwright() as playwright:
        profile = Profile(
            name="status-live",
            storage_state_path=tmp_path / "status-live-state.json",
        )
        session = BrowserSession(
            playwright=playwright,
            settings=settings,
            profile=profile,
            auth_backend=cert,
        )
        reader = StatusReader(
            browser_session=session,
            cert_backend=cert,
            cache=StatusCache(tmp_path / "cache", ttl_s=settings.aeat_status_cache_ttl_s),
            settings=settings,
            tax_id=cert.sha256_thumbprint,
        )
        async with reader:
            records = await reader.fetch_expedientes(use_cache=False)

    assert isinstance(records, tuple)
    assert all(record.expediente_id for record in records)
