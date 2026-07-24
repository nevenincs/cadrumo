"""Real-behavior gate for the `just playwright-doctor` provisioning probe.

Every assertion here forces the REAL condition it names: a real Playwright
launch of a real, provisioned channel for the success path, and a real launch
failure against a channel name that cannot exist for the failure path. No
mocks, stubs, monkeypatches, or hand-computed expectations.
"""

from __future__ import annotations

import pytest

from cadrumo.core.config import Settings

from ..playwright_doctor import remediation_for_channel, run_doctor

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_remediation_for_chrome_names_system_install_and_the_root_caveat() -> None:
    """The `chrome` channel's remediation must name the exact command and the Linux-root constraint."""
    remediation = remediation_for_channel("chrome")
    assert "playwright install chrome" in remediation
    assert "system" in remediation.lower()
    assert "root" in remediation.lower() or "apt" in remediation.lower()


def test_remediation_for_chromium_names_the_matching_install_command() -> None:
    """A non-chrome channel's remediation must name that exact channel, not a hardcoded 'chromium'."""
    remediation = remediation_for_channel("chromium")
    assert "playwright install chromium" in remediation


def test_remediation_never_recommends_the_wrong_browser_for_the_configured_channel() -> None:
    """The `chrome` remediation must not tell the operator to install chromium instead."""
    remediation = remediation_for_channel("chrome")
    assert "playwright install chromium" not in remediation


def test_run_doctor_succeeds_for_a_real_provisioned_channel() -> None:
    """A real launch-and-close of an actually-provisioned channel exits 0."""
    exit_code = run_doctor(channel="chromium")
    assert exit_code == 0


def test_run_doctor_fails_for_a_channel_that_cannot_exist(capsys: pytest.CaptureFixture[str]) -> None:
    """A real launch attempt against a nonsense channel name fails loudly with the exact remediation."""
    bogus_channel = "definitely-not-a-real-playwright-channel"
    exit_code = run_doctor(channel=bogus_channel)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert bogus_channel in captured.err
    assert f"playwright install {bogus_channel}" in captured.err


def test_run_doctor_defaults_to_the_live_configured_setting() -> None:
    """With no explicit channel, `run_doctor` resolves and probes `Settings.cadrumo_browser_channel`.

    The default settings value is `chrome`, which is provisioned on the test
    workstation (`just env-playwright`), so the settings-driven default path
    exits 0 exactly like an explicit `channel="chrome"` probe would.
    """
    assert Settings().cadrumo_browser_channel == "chrome"
    exit_code = run_doctor()
    assert exit_code == 0
