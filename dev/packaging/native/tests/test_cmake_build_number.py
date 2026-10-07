"""Frozen source metadata does not require a version-control executable."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _script(directory: Path, source: Path) -> Path:
    script = directory / "build-number.cmake"
    script.write_text(
        f'set(PROJECT_SOURCE_DIR "{source.as_posix()}")\n'
        f'include("{(REPO_ROOT / "native/cmake/BuildNumber.cmake").as_posix()}")\n'
        'file(WRITE "${CMAKE_CURRENT_LIST_DIR}/number.txt" "${CADRUMO_BUILD_NUMBER}")\n',
        encoding="utf-8",
    )
    return script


def test_supplied_snapshot_number_needs_no_git(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    environment = dict(os.environ, PATH="")
    result = run_command(
        [cmake, "-DCADRUMO_BUILD_NUMBER=2086", "-P", str(_script(tmp_path, tmp_path))],
        cwd=tmp_path,
        environment=environment,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "number.txt").read_text(encoding="utf-8") == "2086"
