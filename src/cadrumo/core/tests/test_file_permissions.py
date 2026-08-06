"""Policy tests for best-effort file-permission hardening.

These tests pin the plaintext compatibility helper's non-raising contract:
POSIX permission failures leave a debug breadcrumb, and Windows ACL tightening
cannot block indefinitely behind a wedged ``icacls.exe`` child process.

See Also:
    :func:`~core.file_permissions.restrict_file_permissions`
        Public hardening primitive for legacy/plaintext auth-state files.
    :func:`~core.file_permissions._run_permission_command`
        Time-bounded subprocess wrapper used by the Windows ACL branch.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from ..file_permissions import _restrict_posix_file_permissions, _run_permission_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_posix_file_permission_failures_are_logged(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    """The helper must leave a debug breadcrumb when POSIX chmod fails."""

    missing_path = tmp_path / "missing-auth-state.json"
    caplog.set_level(logging.DEBUG, logger=_restrict_posix_file_permissions.__module__)

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
