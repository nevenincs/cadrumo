"""Real-behavior gate for the `just doctor-browser` provisioning probe.

The success path launches the real, provisioned bundled Chromium. The failure
path points the product's storage root at an empty one, so the
real launch fails exactly where the product would.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.core.config import override_settings

from ..playwright_doctor import REMEDIATION, run_doctor

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_remediation_names_the_bundled_chromium_install_command() -> None:
    """The remediation names the exact bundled-Chromium install command."""
    assert "playwright install chromium" in REMEDIATION


def test_run_doctor_succeeds_for_the_real_provisioned_chromium() -> None:
    """A real launch-and-close of the provisioned bundled Chromium exits 0.

    This launches a browser, so it fails on a host that has not run
    ``playwright install`` -- a red that reports the host rather than the code.
    The provisioned browser lives beneath the operator's storage root, which test
    isolation replaces, so the root is recovered from the bootstrap's driver pin.
    """
    with override_settings(cadrumo_storage_root=Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]).parents[1]):
        assert run_doctor() == 0


def test_run_doctor_fails_with_remediation_when_chromium_is_not_provisioned(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real launch against an empty browser directory fails loudly with the exact remediation."""
    with override_settings(cadrumo_storage_root=tmp_path):
        exit_code = run_doctor()
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not launchable" in captured.err
    assert "playwright install chromium" in captured.err
