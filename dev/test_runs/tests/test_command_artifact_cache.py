"""Development CLIs own their canonical artifact cache without a pytest bootstrap."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("wrapped", [False, True], ids=["standalone-tool", "logged-command"])
@pytest.mark.parametrize("override", ["absent", "blank", "explicit"])
def test_a_real_command_shares_source_scans_without_a_pytest_or_artifact_root_environment(
    tmp_path: Path, wrapped: bool, override: str
) -> None:
    environment, expected = _command_environment(tmp_path, override)
    source = tmp_path / "source.py"
    source.write_text("observed source\n", encoding="utf-8")
    command = [sys.executable, "-m", "dev.test_runs.tests.artifact_cache_probe", str(source)]
    if wrapped:
        command = [
            sys.executable,
            "-m",
            "dev.test_runs.command",
            "--family",
            "test-runs",
            "--label",
            "artifact-cache-probe",
            "--",
            *command,
        ]
    result = run_audited_process(command, cwd=REPO_ROOT, env=environment, capture_output=True, text=True, timeout=120)
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _probe_payload(result.stdout)
    assert payload["lines"] == ["observed source"]
    assert len(list((expected / "cli-cache-probe").glob("*/result.pickle"))) == 1
    if wrapped:
        _assert_logged_run(tmp_path, expected, payload)


def _command_environment(tmp_path: Path, override: str) -> tuple[dict[str, str], Path]:
    """Remove inherited pytest/run ownership while pinning only the normal cache/log locations."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("CADRUMO_TEST_", "PYTEST_"))
        and name
        not in {
            "CADRUMO_RUN_ARTIFACT_ROOT",
            "CADRUMO_DEV_RUN_ROOT",
            "CADRUMO_DEV_ARTIFACTS_DIR",
            "CADRUMO_DEV_CACHE_DIR",
            "CADRUMO_DEV_SCRATCH_DIR",
        }
    }
    environment["CADRUMO_DEV_CACHE_ROOT"] = str(tmp_path / "development-cache")
    environment["CADRUMO_TEST_LOG_ROOT"] = str(tmp_path / "run-logs")
    expected = tmp_path / "development-cache" / "run-artifacts"
    if override == "explicit":
        expected = tmp_path / "explicit-artifacts"
        environment["CADRUMO_RUN_ARTIFACT_ROOT"] = str(expected)
    elif override == "blank":
        environment["CADRUMO_RUN_ARTIFACT_ROOT"] = "   "
    return environment, expected


def _probe_payload(stdout: str) -> dict[str, object]:
    payload = next(json.loads(line) for line in stdout.splitlines() if line.startswith('{"lines":'))
    assert isinstance(payload, dict)
    fields: dict[str, object] = {}
    for name, value in payload.items():
        assert isinstance(name, str)
        fields[name] = value
    return fields


def _assert_logged_run(tmp_path: Path, expected: Path, payload: dict[str, object]) -> None:
    artifact_environment = payload["artifact_environment"]
    logged_artifact_root = payload["logged_artifact_root"]
    assert isinstance(artifact_environment, str)
    assert isinstance(logged_artifact_root, str)
    assert Path(artifact_environment).resolve() == expected.resolve()
    assert Path(logged_artifact_root).resolve() == expected.resolve()
    metadata = next((tmp_path / "run-logs" / "logs" / "test-runs").glob("*/*/run.json"))
    assert json.loads(metadata.read_text(encoding="utf-8"))["exit_status"] == 0
