"""An exit-5 run names the unresolved request instead of only saying nothing ran."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT
from dev.test_runs.logging import no_tests_diagnosis

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_missing_file_is_named_with_the_request_that_asked_for_it(tmp_path: Path) -> None:
    lines = no_tests_diagnosis(["tests/test_absent.py::test_x"], tmp_path)

    assert len(lines) == 1
    assert lines[0].startswith("ERROR: file or directory not found: tests/test_absent.py")
    assert "test_absent.py::test_x" in lines[0]


def test_an_existing_file_with_a_node_suffix_is_flagged_as_unverifiable(tmp_path: Path) -> None:
    (tmp_path / "test_here.py").write_text("", encoding="utf-8")

    lines = no_tests_diagnosis(["test_here.py::test_typo"], tmp_path)

    assert len(lines) == 1
    assert lines[0].startswith("NOTE:")
    assert "-n 0" in lines[0]


def test_existing_plain_paths_produce_no_diagnosis(tmp_path: Path) -> None:
    (tmp_path / "test_here.py").write_text("", encoding="utf-8")

    assert no_tests_diagnosis(["test_here.py", "."], tmp_path) == ()


def test_the_wrapper_prints_the_missing_path_under_xdist(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("CADRUMO_TEST_RUN_ROOT", None)
    environment.pop("CADRUMO_TEST_RUN_SCRATCH", None)

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-n", "2", "dev/no_such_directory/test_absent.py::test_x"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode == 5, output[-2000:]
    assert "file or directory not found: dev/no_such_directory/test_absent.py" in output
