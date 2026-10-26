"""Action timings survive refusals without retaining command or secret data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ..build_timing import measure_build
from ..cmake_build import run_configured_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_failed_nested_phase_and_total_are_retained_without_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUILD_PRIVATE_TOKEN", "must-not-be-recorded")
    with (
        pytest.raises(ValueError, match="fixture refused"),
        measure_build(tmp_path, "fixture") as timings,
        timings.phase("admission"),
    ):
        raise ValueError("fixture refused")
    contents = next((tmp_path / "timings").glob("fixture-*.json")).read_text()
    assert "must-not-be-recorded" not in contents
    assert "BUILD_PRIVATE_TOKEN" not in contents
    report = json.loads(contents)
    assert [phase["phase"] for phase in report["phases"]] == ["admission", "total"]
    assert all(phase["outcome"] == "fail" and phase["wall_seconds"] >= 0 for phase in report["phases"])


def test_command_failure_marks_enclosing_intervals_without_changing_exit_code(tmp_path: Path) -> None:
    with measure_build(tmp_path, "fixture") as timings:
        result = run_configured_command(tmp_path, {}, [sys.executable, "-c", "raise SystemExit(7)"], timings=timings)
    assert result.returncode == 7
    report = json.loads(timings.path.read_text())
    assert report["command_exit_codes"] == [7]
    assert [(phase["phase"], phase["outcome"]) for phase in report["phases"]] == [
        ("builder-admission", "pass"),
        ("configured-command", "fail"),
        ("total", "fail"),
    ]
