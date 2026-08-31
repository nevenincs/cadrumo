"""Correctness gates for the reusable cold-process CLI profiler."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .cli_performance import profile_cli_path, verify_cli_profiler_instrumentation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_resolution_and_invocation_are_independent_fresh_processes(tmp_path: Path) -> None:
    profile = profile_cli_path(("config", "profile", "list"), storage_root=tmp_path)

    assert profile.resolution.phase == "resolution"
    assert profile.invocation.phase == "invocation"
    assert profile.resolution.child_pid not in {os.getpid(), profile.invocation.child_pid}
    assert profile.invocation.child_pid != os.getpid()
    assert profile.resolution.command_path == ("config", "profile", "list")
    assert profile.invocation.command_path == profile.resolution.command_path
    assert profile.resolution.initial_filesystem_digest == profile.invocation.initial_filesystem_digest
    assert profile.resolution.observed_root_identity != profile.invocation.observed_root_identity
    assert profile.resolution.wall_seconds > 0
    assert profile.invocation.wall_seconds > 0
    assert profile.resolution.exit_code == 0
    assert profile.invocation.exit_code == 0
    assert profile.invocation.stdout


def test_profiler_reports_real_import_model_and_filesystem_observations(tmp_path: Path) -> None:
    profile = profile_cli_path(("config", "profile", "list"), storage_root=tmp_path)

    assert "cadrumo.entrypoints.cli" in profile.resolution.imported_modules
    assert set(profile.resolution.import_families) == {"registry", "crypto", "custody", "keyring", "storage"}
    assert all(not Path(path).is_absolute() for path in profile.invocation.filesystem_created)
    assert profile.invocation.filesystem_operations
    assert all(count > 0 for count in profile.invocation.filesystem_operations.values())
    assert profile.invocation.storage_operation_calls
    assert all(count > 0 for count in profile.invocation.storage_operation_calls.values())


def test_machine_envelope_is_independent_of_cli_output_and_omits_arguments(tmp_path: Path) -> None:
    profile = profile_cli_path((), invocation_args=("--version",), storage_root=tmp_path)

    assert profile.invocation.exit_code == 0
    assert profile.invocation.stdout.strip()
    assert profile.invocation.stderr == ""
    assert profile.invocation.command_path == ()
    assert not hasattr(profile.invocation, "invocation_args")


def test_profiler_enforces_child_timeout(tmp_path: Path) -> None:
    profile = profile_cli_path((), invocation_args=("--version",), storage_root=tmp_path, timeout=0.001)

    assert profile.resolution.failure_kind == "timeout"
    assert profile.invocation.failure_kind == "timeout"
    assert profile.resolution.exit_code == 124
    assert profile.resolution.stderr == ""


def test_profiler_rejects_nonpositive_timeout() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        profile_cli_path((), invocation_args=("--version",), timeout=0)


def test_planted_instrumentation_probe_bites_for_alias_native_storage_and_pydantic() -> None:
    observation = verify_cli_profiler_instrumentation()

    assert observation.exit_code == 0
    assert observation.failure_kind == "none"
    assert observation.pydantic_model_constructions >= 2
    assert observation.filesystem_operations["open.write"] >= 2
    assert "aliased-pathlib.txt" in observation.filesystem_created
    assert "aliased-native.bin" in observation.filesystem_created
    assert any(key.endswith(".path_safety:safe_repository_id") for key in observation.storage_operation_calls)
