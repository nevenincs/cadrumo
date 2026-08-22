"""Real-process gates for quiet-runner calibration orchestration."""

from __future__ import annotations

from math import isfinite
from pathlib import Path

import pytest

from cadrumo.tests.cli_performance import PerformanceCalibrationPolicy, calibrate_cli_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MINIMUM_POLICY = PerformanceCalibrationPolicy(warmup_runs=1, sample_count=3)


def test_calibration_excludes_warmup_and_retains_fresh_alternating_pairs(tmp_path: Path) -> None:
    calibration = calibrate_cli_path((), invocation_args=("--version",), storage_root=tmp_path, policy=_MINIMUM_POLICY)

    assert len(calibration.command_profiles) == _MINIMUM_POLICY.sample_count
    assert len(calibration.control_profiles) == _MINIMUM_POLICY.sample_count
    assert calibration.measured_pair_orders == ("control-first", "command-first", "control-first")
    observations = tuple(
        observation
        for command, control in zip(calibration.command_profiles, calibration.control_profiles, strict=True)
        for observation in (command.resolution, command.invocation, control.resolution, control.invocation)
    )
    assert len({observation.child_pid for observation in observations}) == len(observations)
    assert all(observation.failure_kind == "none" and observation.exit_code == 0 for observation in observations)
    assert isfinite(calibration.resolution_control_ratio)
    assert isfinite(calibration.invocation_control_ratio)


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
