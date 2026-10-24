"""Browser work without a provisioned build is a typed, recoverable refusal.

The readiness check reads a real browsers root through the setup probe. The
launch guard runs a real Playwright driver against an empty browser cache, so
its refusal must come from the session's own provisioning check rather than
from Playwright's missing-executable error. The factory refuses before the
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
from ......application.operator_actions.catalogue import lookup_action
from ......application.provisioning_browser import BROWSER_PROVISION_ACTION_ID, required_browser_builds
from ......application.provisioning_contracts import ProvisioningPreconditionCondition
from ......core.config import Settings
from ......core.errors.error_codes import (
    ErrorCategory,
    build_error_envelope,
    get_registered_error_code,
    render_error_text,
    resolve_error_message,
)
from ..errors import BrowserError, BrowserFailureMode, BrowserNotReadyError, BrowserNotUsableError
from ..factory import create_browser_session, opened_browser_page, shared_playwright_runtime
from ..profile import Profile
from ..session import BrowserSession, require_browser_ready

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


async def _launch_refusal() -> BrowserError:
    async with async_playwright() as playwright:
        session = BrowserSession(
            playwright,
            Settings(),
            Profile(name="provisioning-refusal", locale="es-ES", timezone_id="Europe/Madrid"),
        )
        with pytest.raises(BrowserError) as raised:
            await session.create_context()
        return raised.value


def _profile(name: str) -> Profile:
    return Profile(name=name, locale="es-ES", timezone_id="Europe/Madrid")


def _marked_browser_root(root: Path) -> Path:
    """A browsers root whose completion markers satisfy the setup probe without any executable."""
    builds = required_browser_builds()
    assert builds is not None
    for build in builds:
        directory = root / build.directory_name
        directory.mkdir(parents=True)
        (directory / "INSTALLATION_COMPLETE").write_text("", encoding="utf-8")
    return root


def _assert_names_the_browser_setup(error: BrowserError, browsers_root: Path) -> None:
    assert isinstance(error, BrowserNotReadyError)
    assert not isinstance(error, BrowserNotUsableError)
    registered = get_registered_error_code(error)
    assert registered.category is ErrorCategory.REFUSED
    assert registered.code == "REFUSED_BROWSER_NOT_READY"
    assert registered.message_key == "adapters.browser.errors.not_provisioned"
    assert error.failure_mode == BrowserFailureMode.BROWSER_NOT_PROVISIONED.value
    assert error.__cause__ is None
    # A catalogue key, not rendered text: the stored detail renders it in the reader's language.
    assert error.translated_message == "adapters.browser.errors.not_provisioned"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    assert verdict.evidence[0].values["browser_cache_root"] == str(browsers_root)
    assert verdict.action is not None
    assert verdict.action.action_id == BROWSER_PROVISION_ACTION_ID
    assert lookup_action(verdict.action.action_id).target_command_key == "config.provision.browser"


def test_missing_bundled_chromium_names_the_provisioning_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", str(tmp_path / "empty-cache"))

    error = asyncio.run(_launch_refusal())

    _assert_names_the_browser_setup(error, tmp_path / "empty-cache")


def test_readiness_check_refuses_an_empty_root_and_admits_a_complete_one(tmp_path: Path) -> None:
    empty = tmp_path / "empty-cache"
    with pytest.raises(BrowserError) as raised:
        require_browser_ready(Settings(cadrumo_playwright_browsers_dir=empty), profile_name="readiness")
    _assert_names_the_browser_setup(raised.value, empty)

    marked = _marked_browser_root(tmp_path / "marked-cache")
    require_browser_ready(Settings(cadrumo_playwright_browsers_dir=marked), profile_name="readiness")


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

    _assert_names_the_browser_setup(raised.value, empty)
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == driver_root
    assert {child.pid for child in psutil.Process().children(recursive=True)} <= children_before


@pytest.mark.asyncio
async def test_page_factory_refuses_a_missing_browser_on_a_shared_runtime(tmp_path: Path) -> None:
    empty = tmp_path / "empty-cache"
    settings = Settings(cadrumo_playwright_browsers_dir=empty)
    async with shared_playwright_runtime() as playwright:
        with pytest.raises(BrowserError) as raised:
            async with opened_browser_page(playwright, settings, _profile("page-refusal")):
                pytest.fail("a page opened without a provisioned browser")

    _assert_names_the_browser_setup(raised.value, empty)


def test_a_browser_setup_cannot_repair_is_refused_without_offering_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed Playwright whose browser manifest is gone cannot be repaired by setup."""
    damaged = tmp_path / "damaged-playwright"
    damaged.mkdir()
    module = ModuleType("playwright")
    module.__spec__ = ModuleSpec("playwright", None, origin=str(damaged / "__init__.py"))
    monkeypatch.setitem(sys.modules, "playwright", module)

    with pytest.raises(BrowserNotUsableError) as raised:
        require_browser_ready(Settings(cadrumo_playwright_browsers_dir=tmp_path / "cache"), profile_name="damaged")

    error = raised.value
    registered = get_registered_error_code(error)
    assert registered.category is ErrorCategory.REFUSED
    assert registered.code == "REFUSED_BROWSER_NOT_USABLE"
    # A reader holding only the code renders the code's own sentence, which offers no setup.
    assert registered.message_key == "adapters.browser.errors.not_usable"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_MANIFEST_READABLE.value
    assert verdict.action is None
    assert error.translated_message == "adapters.browser.errors.not_usable"
    sentence = resolve_error_message(error, locale="en")
    assert "browser for the tax agency website" in sentence
    assert "set it up" not in sentence.lower()


def test_the_rendered_refusal_is_its_sentence_alone(tmp_path: Path) -> None:
    """The failure mode and the browser profile stay internal; the verdict carries the action."""
    with pytest.raises(BrowserNotReadyError) as raised:
        require_browser_ready(Settings(cadrumo_playwright_browsers_dir=tmp_path / "empty"), profile_name="internal")
    error = raised.value

    text = render_error_text(error)
    assert text.splitlines()[1:] == []
    assert resolve_error_message(error) in text
    for internal in ("browser_not_provisioned", "Failure mode", "internal", "Chromium"):
        assert internal not in text
    assert build_error_envelope(error).context is None
    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.context == ()
    assert detail.message_key == "adapters.browser.errors.not_provisioned"
    assert detail.precondition_verdict() == error.terminal_precondition_verdict
