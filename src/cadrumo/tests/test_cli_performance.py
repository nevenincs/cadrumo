"""Correctness gates for the reusable cold-process CLI profiler."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from .cli_performance import profile_cli_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_resolution_and_invocation_are_independent_fresh_processes(tmp_path: Path) -> None:
    profile = profile_cli_path(("config", "profile", "list"), storage_root=tmp_path)

    assert profile.resolution.phase == "resolution"
    assert profile.invocation.phase == "invocation"
    assert profile.resolution.child_pid not in {os.getpid(), profile.invocation.child_pid}
    assert profile.invocation.child_pid != os.getpid()
    assert profile.resolution.argv == ("config", "profile", "list")
    assert profile.invocation.argv == profile.resolution.argv
    assert profile.resolution.wall_seconds > 0
    assert profile.invocation.wall_seconds > 0
    assert profile.resolution.exit_code == 0
    assert profile.invocation.exit_code == 0
    assert profile.invocation.stdout


def test_profiler_reports_real_import_model_and_filesystem_observations(tmp_path: Path) -> None:
    profile = profile_cli_path(("config", "profile", "list"), storage_root=tmp_path)

    assert "cadrumo.entrypoints.cli" in profile.resolution.imported_modules
    assert set(profile.resolution.import_families) == {"registry", "crypto", "custody", "keyring", "storage"}
    assert profile.resolution.pydantic_model_constructions >= 0
    assert profile.invocation.pydantic_model_constructions >= 0
    assert all(not Path(path).is_absolute() for path in profile.invocation.filesystem_created)
    assert all(count > 0 for count in profile.invocation.filesystem_operations.values())
    assert all(count > 0 for count in profile.invocation.storage_operation_calls.values())


def test_machine_envelope_is_independent_of_cli_output(tmp_path: Path) -> None:
    profile = profile_cli_path(("--version",), storage_root=tmp_path)

    assert profile.invocation.exit_code == 0
    assert profile.invocation.stdout.strip()
    assert profile.invocation.stderr == ""
    assert profile.invocation.argv == ("--version",)


def test_profiler_enforces_child_timeout(tmp_path: Path) -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        profile_cli_path(("--version",), storage_root=tmp_path, timeout=0.001)


def test_profiler_rejects_nonpositive_timeout() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        profile_cli_path(("--version",), timeout=0)
