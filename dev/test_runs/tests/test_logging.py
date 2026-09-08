"""Integration contract for pytest's per-run storage confinement."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.serial]


def test_real_child_pytest_confines_cache_and_basetemp_to_its_run(tmp_path: Path) -> None:
    report = tmp_path / "pytest-paths.json"
    environment = os.environ.copy()
    environment.pop("CADRUMO_TEST_RUN_ROOT", None)
    environment["CADRUMO_PYTEST_PATH_PROBE"] = str(report)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n0",
            "dev/test_runs/tests/path_probe.py",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    paths = json.loads(report.read_text(encoding="utf-8"))
    run_root = Path(paths["run_root"]).resolve()
    assert Path(paths["cache"]).resolve() == run_root / "cache" / "pytest"
    assert Path(paths["basetemp"]).resolve() == run_root / "scratch" / "pytest"
    assert Path(paths["stdlib_temp"]).resolve() == run_root / "scratch"
    assert Path(paths["storage_root"]).resolve().parent == run_root / "scratch"
