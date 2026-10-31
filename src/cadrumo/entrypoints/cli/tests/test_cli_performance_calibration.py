"""Real-process gates for quiet-runner calibration orchestration."""

from __future__ import annotations

import asyncio
from math import isfinite
from pathlib import Path
from typing import Any

import pytest

from . import cli_performance
from .cli_performance import (
    CliPerformanceObservation,
    CliPerformanceProfile,
    PerformanceCalibrationPolicy,
    calibrate_cli_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MINIMUM_POLICY = PerformanceCalibrationPolicy(warmup_runs=1, sample_count=3)


def test_calibration_excludes_warmup_and_retains_fresh_alternating_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launches: list[int] = []
    run = cli_performance.run_audited_process

    def counted_launch(*args: Any, **kwargs: Any) -> Any:
        def record(process: asyncio.subprocess.Process) -> None:
            launches.append(process.pid)

        return run(*args, **kwargs, after_spawn=record)

    monkeypatch.setattr(cli_performance, "run_audited_process", counted_launch)
    calibration = calibrate_cli_path((), invocation_args=("--version",), storage_root=tmp_path, policy=_MINIMUM_POLICY)

    assert len(calibration.command_profiles) == _MINIMUM_POLICY.sample_count
    assert len(calibration.control_profiles) == _MINIMUM_POLICY.sample_count
    assert calibration.measured_pair_orders == ("control-first", "command-first", "control-first")
    observations = tuple(
        observation
        for command, control in zip(calibration.command_profiles, calibration.control_profiles, strict=True)
        for observation in (command.resolution, command.invocation, control.resolution, control.invocation)
    )
    # PID values can be recycled after a child exits. Each callback instead
    # witnesses a distinct process launch, and each envelope identifies that
    # launch's PID. The first four launches are the discarded warmup pair.
    assert len(launches) == 4 * (_MINIMUM_POLICY.warmup_runs + _MINIMUM_POLICY.sample_count)
    ordered = tuple(
        observation.child_pid
        for command, control, order in zip(
            calibration.command_profiles, calibration.control_profiles, calibration.measured_pair_orders, strict=True
        )
        for profile in ((command, control) if order == "command-first" else (control, command))
        for observation in (profile.resolution, profile.invocation)
    )
    assert tuple(launches[4 * _MINIMUM_POLICY.warmup_runs :]) == ordered
    assert all(observation.failure_kind == "none" and observation.exit_code == 0 for observation in observations)
    assert isfinite(calibration.resolution_control_ratio)
    assert isfinite(calibration.invocation_control_ratio)


def test_calibration_keeps_distinct_launch_observations_when_pids_are_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def profile(path: tuple[str, ...], **_kwargs: Any) -> CliPerformanceProfile:
        calls.append(path)

        def observation(phase: Any) -> CliPerformanceObservation:
            return CliPerformanceObservation(
                phase=phase,
                command_path=path,
                child_pid=42,
                wall_seconds=float(len(calls)),
                imported_modules=(),
                import_families={},
                pydantic_model_constructions=0,
                filesystem_created=(),
                filesystem_modified=(),
                filesystem_deleted=(),
                filesystem_operations={},
                storage_operation_calls={},
                initial_filesystem_digest="",
                observed_root_identity="",
                exit_code=0,
                stdout="",
                stderr="",
                failure_kind="none",
            )

        return CliPerformanceProfile(resolution=observation("resolution"), invocation=observation("invocation"))

    monkeypatch.setattr(cli_performance, "profile_cli_path", profile)
    calibration = calibrate_cli_path(("app",), policy=_MINIMUM_POLICY)

    assert calls == [("app",), (), (), ("app",), ("app",), (), (), ("app",)]
    assert calibration.measured_pair_orders == ("control-first", "command-first", "control-first")
    assert calibration.command_resolution.samples_seconds == (4, 5, 8)
    assert calibration.control_resolution.samples_seconds == (3, 6, 7)
    assert all(profile.resolution.child_pid == 42 for profile in calibration.command_profiles)


def test_calibration_refuses_timeout_instead_of_aggregating_it(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="observation failed: failure_kind=timeout"):
        calibrate_cli_path(
            (),
            invocation_args=("--version",),
            storage_root=tmp_path,
            timeout=0.001,
            policy=_MINIMUM_POLICY,
        )


def test_calibration_refuses_nonzero_exit_instead_of_aggregating_it(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="invocation observation failed: failure_kind=none, exit_code=2"):
        calibrate_cli_path(
            (),
            invocation_args=("--not-a-real-option",),
            storage_root=tmp_path,
            policy=_MINIMUM_POLICY,
        )
