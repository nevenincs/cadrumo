"""Real configuration coverage for the installed-browser smoke environment."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from dev.packaging.smoke_browser import _browser_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_browser_smoke_environment_reaches_canonical_settings(tmp_path: Path) -> None:
    """The smoke selects installed Chromium through the production Settings boundary."""
    env = _browser_env(tmp_path)
    code = "\n".join(
        (
            "from cadrumo.core.config import load_settings",
            "settings = load_settings()",
            "assert settings.cadrumo_browser_channel == 'chromium'",
            "assert settings.cadrumo_browser_headless is True",
            "print('canonical-browser-env-ok')",
        )
    )

    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-authored source.
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "canonical-browser-env-ok\n"
