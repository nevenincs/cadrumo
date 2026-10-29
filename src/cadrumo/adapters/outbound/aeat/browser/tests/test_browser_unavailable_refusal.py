"""Browser work without an available build is a typed refusal.

The readiness check locates the browser by the completion markers of its
builds. The launch guard runs a real Playwright driver against an empty browser
cache, so its refusal must come from the session's own readiness check rather
than from Playwright's missing-executable error. The factory refuses before the
Playwright driver starts at all.
"""

from __future__ import annotations

import asyncio
import os
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

import psutil
import pytest
from playwright.async_api import async_playwright

from ......application.operations.error_detail import build_operation_error_detail
from ......application.probe_outcomes import ProbePreconditionCondition
from ......core.config import Settings
from ......core.errors.error_codes import (
    ErrorCategory,
    build_error_envelope,
    get_registered_error_code,
    render_error_text,
    resolve_error_message,
)
from ..errors import BrowserError, BrowserFailureMode, BrowserNotReadyError
from ..factory import create_browser_session, opened_browser_page, shared_playwright_runtime
from ..profile import Profile
from ..session import BrowserSession, require_browser_ready
from .installed_builds import place_installed_builds

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


async def _launch_refusal() -> BrowserError:
    async with async_playwright() as playwright:
        session = BrowserSession(
            playwright,
            Settings(),
            Profile(name="unavailable-refusal", locale="es-ES", timezone_id="Europe/Madrid"),
        )
        with pytest.raises(BrowserError) as raised:
            await session.create_context()
        return raised.value


def _profile(name: str) -> Profile:
    return Profile(name=name, locale="es-ES", timezone_id="Europe/Madrid")


def _installed_browser(tmp_path: Path) -> Settings:
    """Settings whose browsers root holds the builds the installed driver launches."""
    browsers = tmp_path / "installed-cache"
    place_installed_builds(browsers)
    return Settings(cadrumo_local_storage_root=tmp_path / "storage", cadrumo_playwright_browsers_dir=browsers)


def _assert_names_the_unavailable_browser(error: BrowserError, browsers_root: Path) -> None:
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
    assert verdict.failed_condition_id == ProbePreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    # The verdict is published with every refusal, so it names why the browser was not
    # located, never the folder.
    assert verdict.evidence[0].values["chromium_installed"] is False
    assert not [value for value in verdict.evidence[0].values.values() if str(browsers_root) in str(value)]
    assert verdict.action is None


def test_missing_bundled_chromium_is_refused_as_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", str(tmp_path / "empty-cache"))

    error = asyncio.run(_launch_refusal())

    _assert_names_the_unavailable_browser(error, tmp_path / "empty-cache")


def test_readiness_check_refuses_an_empty_root_and_admits_a_complete_one(tmp_path: Path) -> None:
    empty = tmp_path / "empty-cache"
    with pytest.raises(BrowserError) as raised:
        require_browser_ready(Settings(cadrumo_playwright_browsers_dir=empty), profile_name="readiness")
    _assert_names_the_unavailable_browser(raised.value, empty)

    require_browser_ready(_installed_browser(tmp_path), profile_name="readiness")


def test_session_factory_refuses_before_the_playwright_driver_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-cache"
    # Starting the driver points PLAYWRIGHT_BROWSERS_PATH at the managed root
    # and spawns a driver child; neither may happen for a refused session.
    driver_root = str(tmp_path / "driver-root-unchanged")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", driver_root)
    children_before = {child.pid for child in psutil.Process().children(recursive=True)}

    with pytest.raises(BrowserError) as raised:
        asyncio.run(
            create_browser_session(Settings(cadrumo_playwright_browsers_dir=empty), _profile("factory-refusal"))
        )

    _assert_names_the_unavailable_browser(raised.value, empty)
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == driver_root
    assert {child.pid for child in psutil.Process().children(recursive=True)} <= children_before


@pytest.mark.asyncio
async def test_page_factory_refuses_a_missing_browser_on_a_shared_runtime(tmp_path: Path) -> None:
    empty = tmp_path / "empty-cache"
    settings = Settings(cadrumo_playwright_browsers_dir=empty)
    async with shared_playwright_runtime() as playwright:
        with pytest.raises(BrowserError) as raised:
            async with opened_browser_page(playwright, settings, _profile("page-refusal")):
                pytest.fail("a page opened without an available browser")

    _assert_names_the_unavailable_browser(raised.value, empty)


def test_an_unreadable_driver_is_refused_as_an_unavailable_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed Playwright whose browser manifest is gone leaves no browser to use."""
    damaged = tmp_path / "damaged-playwright"
    damaged.mkdir()
    module = ModuleType("playwright")
    module.__spec__ = ModuleSpec("playwright", None, origin=str(damaged / "__init__.py"))
    monkeypatch.setitem(sys.modules, "playwright", module)

    with pytest.raises(BrowserNotReadyError) as raised:
        require_browser_ready(Settings(cadrumo_playwright_browsers_dir=tmp_path / "cache"), profile_name="damaged")

    error = raised.value
    registered = get_registered_error_code(error)
    assert registered.category is ErrorCategory.REFUSED
    assert registered.code == "REFUSED_BROWSER_NOT_READY"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProbePreconditionCondition.PLAYWRIGHT_BROWSER_MANIFEST_READABLE.value
    assert verdict.action is None


def test_the_rendered_refusal_is_its_sentence_alone(tmp_path: Path) -> None:
    """The failure mode and the browser profile stay internal; the verdict carries the action."""
    with pytest.raises(BrowserNotReadyError) as raised:
        require_browser_ready(Settings(cadrumo_playwright_browsers_dir=tmp_path / "empty"), profile_name="internal")
    error = raised.value

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
