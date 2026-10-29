"""A launch that finds no browser build is a typed refusal, not Playwright's raw error.

Each case runs a real Playwright driver against an empty browsers folder, so
the refusal comes from the launch itself finding nothing to start.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from ......application.operations.error_detail import build_operation_error_detail
from ......core.config import Settings, override_settings
from ......core.errors.error_codes import (
    ErrorCategory,
    build_error_envelope,
    get_registered_error_code,
    render_error_text,
    resolve_error_message,
)
from ..errors import BrowserError, BrowserFailureMode, BrowserNotReadyError, BrowserPreconditionCondition
from ..factory import create_browser_session, opened_browser_page, shared_playwright_runtime
from ..profile import Profile
from ..session import BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _profile(name: str) -> Profile:
    return Profile(name=name, locale="es-ES", timezone_id="Europe/Madrid")


def _assert_names_the_unavailable_browser(error: BrowserError) -> None:
    assert isinstance(error, BrowserNotReadyError)
    registered = get_registered_error_code(error)
    assert registered.category is ErrorCategory.REFUSED
    assert registered.code == "REFUSED_BROWSER_NOT_READY"
    assert registered.message_key == "adapters.browser.errors.not_available"
    assert error.failure_mode == BrowserFailureMode.BROWSER_NOT_AVAILABLE.value
    assert error.__cause__ is None
    # A catalogue key, not rendered text: the stored detail renders it in the reader's language.
    assert error.translated_message == "adapters.browser.errors.not_available"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == BrowserPreconditionCondition.BROWSER_AVAILABLE.value
    assert verdict.evidence[0].values["browser_available"] is False
    assert verdict.action is None


async def _launch_refusal(empty_root: Path) -> BrowserError:
    async with async_playwright() as playwright:
        session = BrowserSession(
            playwright,
            Settings(cadrumo_playwright_browsers_dir=empty_root),
            _profile("unavailable-refusal"),
        )
        with pytest.raises(BrowserError) as raised:
            await session.create_context()
        return raised.value


def test_missing_bundled_chromium_is_refused_as_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty-cache"
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(empty))

    error = asyncio.run(_launch_refusal(empty))

    _assert_names_the_unavailable_browser(error)


def test_session_factory_refuses_at_launch_and_leaves_no_session_open(tmp_path: Path) -> None:
    empty = tmp_path / "empty-cache"

    async def attempt() -> BrowserError:
        session = await create_browser_session(Settings(cadrumo_playwright_browsers_dir=empty), _profile("factory"))
        try:
            with pytest.raises(BrowserError) as raised:
                await session.create_context()
            return raised.value
        finally:
            await session.close()

    _assert_names_the_unavailable_browser(asyncio.run(attempt()))


@pytest.mark.asyncio
async def test_page_factory_refuses_a_missing_browser_on_a_shared_runtime(tmp_path: Path) -> None:
    empty = tmp_path / "empty-cache"
    settings = Settings(cadrumo_playwright_browsers_dir=empty)
    with override_settings(cadrumo_playwright_browsers_dir=empty):
        async with shared_playwright_runtime() as playwright:
            with pytest.raises(BrowserError) as raised:
                async with opened_browser_page(playwright, settings, _profile("page-refusal")):
                    pytest.fail("a page opened without an available browser")

    _assert_names_the_unavailable_browser(raised.value)


def test_the_rendered_refusal_is_its_sentence_alone(tmp_path: Path) -> None:
    """The failure mode and the browser profile stay internal; the verdict carries the condition."""
    empty = tmp_path / "empty"

    async def attempt() -> BrowserError:
        session = await create_browser_session(Settings(cadrumo_playwright_browsers_dir=empty), _profile("internal"))
        try:
            with pytest.raises(BrowserError) as raised:
                await session.create_context()
            return raised.value
        finally:
            await session.close()

    error = asyncio.run(attempt())
    assert isinstance(error, BrowserNotReadyError)

    text = render_error_text(error)
    assert text.splitlines()[1:] == []
    assert resolve_error_message(error) in text
    for internal in ("browser_not_available", "Failure mode", "internal", "Chromium"):
        assert internal not in text
    assert build_error_envelope(error).context is None
    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.context == ()
    assert detail.message_key == "adapters.browser.errors.not_available"
    assert detail.precondition_verdict() == error.terminal_precondition_verdict
