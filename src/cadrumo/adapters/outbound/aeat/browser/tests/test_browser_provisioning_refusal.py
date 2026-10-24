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
from pathlib import Path

import psutil
import pytest
from playwright.async_api import async_playwright

from ......application.operator_actions.catalogue import lookup_action
from ......application.provisioning_browser import BROWSER_PROVISION_ACTION_ID, required_browser_builds
from ......application.provisioning_contracts import ProvisioningPreconditionCondition
from ......core.config import Settings
from ......core.i18n.render import tr
from ..errors import BrowserError, BrowserFailureMode
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
    assert error.failure_mode == BrowserFailureMode.BROWSER_NOT_PROVISIONED.value
    assert error.__cause__ is None
    assert error.translated_message == tr("adapters.browser.errors.not_provisioned")
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
    assert raised.value.context is not None
    assert raised.value.context["profile"] == "readiness"

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
