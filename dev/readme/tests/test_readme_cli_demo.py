"""Real bootstrap and identity checks for the generated README CLI demo."""

from __future__ import annotations

import subprocess
import sys

import pytest
from dev._paths import REPO_ROOT
from dev.readme import prepare_cli_demo, render_cli_demo

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_demo_authorities_use_only_cadrumo_product_paths_and_commands() -> None:
    """The renderer and preparer contain no retired product bootstrap or command."""
    assert prepare_cli_demo._CLI_BOOTSTRAP == "from cadrumo.entrypoints.cli import main; main()"
    assert render_cli_demo._CLI_BOOTSTRAP == prepare_cli_demo._CLI_BOOTSTRAP
    assert render_cli_demo.DISPLAY_COMMAND.startswith("aeat app quickfile ")
    assert prepare_cli_demo.DEMO_ROOT == REPO_ROOT / "var" / "readme-demo"


def test_demo_bootstrap_runs_the_real_cadrumo_help_surface() -> None:
    """The exact subprocess bootstrap used by the demo reaches the live Cadrumo CLI."""
    completed = subprocess.run(  # noqa: S603 - executable and bootstrap are repository-owned constants
        [sys.executable, "-c", prepare_cli_demo._CLI_BOOTSTRAP, "--help"],
        cwd=REPO_ROOT,
        env=prepare_cli_demo.demo_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines()[0] == ("CADRUMO - local-first workflow for Spanish tax work with AEAT")
    assert "import aeat" not in completed.stderr
