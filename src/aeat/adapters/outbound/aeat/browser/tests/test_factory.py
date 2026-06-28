"""Tests for the default browser-session factory wrapper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import pytest
from playwright.async_api import BrowserContext, Page, Playwright, Response

from .. import _factory as factory_module
from .._factory import DefaultBrowserSession
from ..profile import Profile
from ..session import BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class ClosingBrowserSession:
    """Concrete session adapter that records close calls."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.close_calls = 0

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: dict[str, object] | None = None,
    ) -> BrowserContext:
        """Keep the protocol shape available for wrapper delegation."""
        raise AssertionError("context creation is outside this close-path test")

    async def navigate(self, page: Page, url: str) -> Response | None:
        """Keep the protocol shape available for wrapper delegation."""
        del page, url
        raise AssertionError("navigation is outside this close-path test")

    async def close(self) -> None:
        """Record that the wrapped session was closed."""
        self.close_calls += 1


class StopFailingPlaywright:
    """Concrete Playwright adapter whose stop path fails with sensitive text."""

    def __init__(self, sensitive_payload: str) -> None:
        self.sensitive_payload = sensitive_payload
        self.stop_calls = 0

    async def stop(self) -> None:
        """Raise a teardown failure carrying data that must not be logged."""
        self.stop_calls += 1
        raise RuntimeError(f"stop failed for {self.sensitive_payload}")


@pytest.mark.asyncio
async def test_default_browser_session_close_redacts_playwright_stop_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Playwright stop failures should leave debug breadcrumbs without payloads."""
    sensitive_payload = str(tmp_path / "profile-12345678Z" / "browser-storage.json")
    profile = Profile(
        name="profile-12345678Z",
        storage_state_path=tmp_path / "browser-storage.json",
        locale="es-ES",
        timezone_id="Europe/Madrid",
    )
    session_adapter = ClosingBrowserSession(profile)
    playwright_adapter = StopFailingPlaywright(sensitive_payload)
    browser_session = DefaultBrowserSession(
        playwright=cast(Playwright, playwright_adapter),
        session=cast(BrowserSession, session_adapter),
    )

    with caplog.at_level(logging.WARNING, logger=factory_module.__name__):
        await browser_session.close()
        await browser_session.close()

    assert session_adapter.close_calls == 1
    assert playwright_adapter.stop_calls == 1

    records = [record for record in caplog.records if record.name == factory_module.__name__]
    rendered = "\n".join(record.getMessage() for record in records)
    assert "default_browser_session: playwright stop failed" in rendered
    assert "resource=<playwright-runtime>" in rendered
    assert "failure=RuntimeError" in rendered
    assert sensitive_payload not in rendered
    assert "12345678Z" not in rendered
    assert "browser-storage.json" not in rendered
    assert all(record.exc_info is None for record in records)
