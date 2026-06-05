"""Real-behavior test: importing aeat.adapters.outbound.llm must not emit to stdout."""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_llm_import_silent() -> None:
    """Importing aeat.adapters.outbound.llm must produce no stdout output."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import aeat.adapters.outbound.llm",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Import failed with returncode {result.returncode}:\n{result.stderr}"
    assert result.stdout == "", f"Import produced unexpected stdout output:\n{result.stdout!r}"
