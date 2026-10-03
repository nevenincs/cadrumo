"""Cancellation of a caller cannot abandon durable profile-worker admission."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile custody"),
    pytest.mark.usefixtures("authority_operation"),
]


def _run_child(tmp_path: Path, mode: str) -> None:
    result = subprocess.run(  # noqa: S603 - fixed Python module and isolated pytest path
        [sys.executable, "-m", "cadrumo.entrypoints.runtime.tests.admission_cancellation_fixture", str(tmp_path), mode],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    assert result.returncode == 0, result.stderr


def test_cancelled_admission_retains_custody_and_execution_binding(tmp_path: Path) -> None:
    _run_child(tmp_path, "cancel")


def test_lazy_submit_can_close_from_caller_task(tmp_path: Path) -> None:
    _run_child(tmp_path, "lazy-close")
