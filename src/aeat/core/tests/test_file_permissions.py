"""Policy tests for best-effort file-permission hardening."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aeat.core.file_permissions import _restrict_posix_file_permissions, _run_permission_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_posix_file_permission_failures_are_logged(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    """The helper must leave a debug breadcrumb when POSIX chmod fails."""

    missing_path = tmp_path / "missing-auth-state.json"

    _restrict_posix_file_permissions(missing_path)

    assert any("chmod failed" in record.message and record.exc_info for record in caplog.records)


def test_permission_command_is_time_bounded() -> None:
    """The Windows ACL helper must not let a wedged icacls child block indefinitely."""

    command = [
        sys.executable,
        "-c",
        "import time; time.sleep(60)",
    ]

    with pytest.raises(subprocess.TimeoutExpired):
        _run_permission_command(command, timeout=0.01)
