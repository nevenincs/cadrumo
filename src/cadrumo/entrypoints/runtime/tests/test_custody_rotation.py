"""Isolated worker-custody proofs for a committed password successor."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile custody"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize("mode", ["success", "uncommitted", "outside", "jump", "unretired"])
def test_password_successor_custody_boundary(tmp_path: Path, mode: str) -> None:
    """A fresh child keeps the process-global worker pin independent per case."""
    result = run_audited_process(
        [sys.executable, "-m", "cadrumo.entrypoints.runtime.tests.custody_rotation_fixture", str(tmp_path), mode],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
