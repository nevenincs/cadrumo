"""Real-behavior test: importing aeat.domain.normatives must not emit to stdout."""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_normatives_import_silent(tmp_path: pytest.TempPathFactory) -> None:
    """Importing aeat.domain.normatives must produce no stdout output."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import aeat.domain.normatives",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Import failed with returncode {result.returncode}:\n{result.stderr}"
    assert result.stdout == "", f"Import produced unexpected stdout output:\n{result.stdout!r}"
