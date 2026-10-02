"""Real-behavior gate for the `just doctor-browser` provisioning probe.

The success path launches the real, provisioned bundled Chromium. The failure
path points Playwright at an empty browser directory so the real launch fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..playwright_doctor import REMEDIATION, run_doctor

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_remediation_names_the_bundled_chromium_install_command() -> None:
    """The remediation names the exact bundled-Chromium install command."""
    assert "playwright install chromium" in REMEDIATION


def test_run_doctor_succeeds_for_the_real_provisioned_chromium() -> None:
    """A real launch-and-close of the provisioned bundled Chromium exits 0.

    This launches a browser, so it fails on a host that has not run
    ``playwright install`` -- a red that reports the host rather than the code.
    """
    assert run_doctor() == 0


def test_run_doctor_fails_with_remediation_when_chromium_is_not_provisioned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real launch against an empty browser directory fails loudly with the exact remediation."""
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    exit_code = run_doctor()
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not launchable" in captured.err
    assert "playwright install chromium" in captured.err
