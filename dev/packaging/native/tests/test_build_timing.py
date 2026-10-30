"""Action timings survive refusals without retaining command or secret data."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from ..build_timing import measure_build
from ..cached_command import _configure_temporary
from ..cargo_command import run_configured_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(autouse=True)
def timing_output_map(tmp_path: Path) -> None:
    """Give synthetic actions the same declared timing owner as CMake builds."""
    (tmp_path / "build-paths.json").write_text(json.dumps({"paths": {"timings": "timings"}}), encoding="utf-8")


def test_cached_command_pins_temporary_environment_to_its_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build-paths.json").write_text(json.dumps({"paths": {"temporary": "temporary"}}), encoding="utf-8")
    monkeypatch.setattr(tempfile, "tempdir", None)
    for name in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(name, str(tmp_path / "external"))
    _configure_temporary(tmp_path)
    expected = str(tmp_path / "temporary")
    assert (tmp_path / "temporary").is_dir()
    assert all(os.environ[name] == expected for name in ("TEMP", "TMP", "TMPDIR"))
    assert tempfile.gettempdir() == expected


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


def test_timing_records_follow_the_declared_output_instead_of_a_parallel_default(tmp_path: Path) -> None:
    (tmp_path / "build-paths.json").write_text(
        json.dumps({"paths": {"timings": "diagnostics/phases"}}), encoding="utf-8"
    )
    with measure_build(tmp_path, "fixture") as timings:
        pass
    assert timings.path.parent == tmp_path / "diagnostics" / "phases"
    assert timings.path.is_file()
    assert not (tmp_path / "timings").exists()


def test_older_output_maps_require_reconfigure_without_creating_an_unmapped_directory(tmp_path: Path) -> None:
    (tmp_path / "build-paths.json").write_text(json.dumps({"paths": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="reconfigure"), measure_build(tmp_path, "fixture"):
        pass
    assert not (tmp_path / "timings").exists()
