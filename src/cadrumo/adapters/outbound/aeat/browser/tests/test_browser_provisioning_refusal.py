"""A bundled-Chromium launch without a provisioned build is a typed, recoverable refusal.

Runs a real Playwright driver against an empty browser cache, so the refusal
must come from the session's own provisioning check rather than from
Playwright's missing-executable error.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from ......application.operator_actions.catalogue import lookup_action
from ......application.provisioning_browser import BROWSER_PROVISION_ACTION_ID
from ......application.provisioning_contracts import ProvisioningPreconditionCondition
from ......core.config import Settings
from ......core.i18n.render import tr
from ..errors import BrowserError, BrowserFailureMode
from ..profile import Profile
from ..session import BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


async def _launch_refusal(channel: str) -> BrowserError:
    async with async_playwright() as playwright:
        session = BrowserSession(
            playwright,
            Settings(cadrumo_browser_channel=channel),
            Profile(name="provisioning-refusal", locale="es-ES", timezone_id="Europe/Madrid"),
        )
        with pytest.raises(BrowserError) as raised:
            await session.create_context()
        return raised.value


@pytest.mark.parametrize("channel", ("chromium", ""))
def test_missing_bundled_chromium_names_the_provisioning_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, channel: str
) -> None:
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "empty-cache"))

    error = asyncio.run(_launch_refusal(channel))

    assert error.failure_mode == BrowserFailureMode.BROWSER_NOT_PROVISIONED.value
    assert error.__cause__ is None
    assert error.translated_message == tr("adapters.browser.errors.not_provisioned")
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    assert verdict.evidence[0].values["browser_cache_root"] == str(tmp_path / "empty-cache")
    assert verdict.action is not None
    assert verdict.action.action_id == BROWSER_PROVISION_ACTION_ID
    assert lookup_action(verdict.action.action_id).target_command_key == "config.provision.browser"
