"""Build identity cache values: empty allocates per build, explicit values freeze, no git needed."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

BUILD_NUMBER = (REPO_ROOT / "native/cmake/BuildNumber.cmake").as_posix()


def _script(directory: Path, source: Path) -> Path:
    script = directory / "build-number.cmake"
    script.write_text(
        f'set(PROJECT_SOURCE_DIR "{source.as_posix()}")\n'
        f'include("{BUILD_NUMBER}")\n'
        'file(WRITE "${CMAKE_CURRENT_LIST_DIR}/number.txt" '
        '"${CADRUMO_BUILD_NUMBER}|${CADRUMO_BUILD_ID}|${CADRUMO_BUILD_DATE}")\n',
        encoding="utf-8",
    )
    return script


def _cmake() -> str:
    cmake = shutil.which("cmake")
    assert cmake is not None, "CMake is a build prerequisite; install it and put it on PATH"
    return cmake


def test_supplied_snapshot_number_needs_no_git(tmp_path: Path) -> None:
    environment = dict(os.environ, PATH="")
    result = run_command(
        [_cmake(), "-DCADRUMO_BUILD_NUMBER=2086", "-P", str(_script(tmp_path, tmp_path))],
        cwd=tmp_path,
        environment=environment,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "number.txt").read_text(encoding="utf-8") == "2086||"


def test_empty_values_leave_the_identity_to_each_build(tmp_path: Path) -> None:
    result = run_command([_cmake(), "-P", str(_script(tmp_path, tmp_path))], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "number.txt").read_text(encoding="utf-8") == "||"


@pytest.mark.parametrize(
    ("definition", "refusal"),
    [
        ("CADRUMO_BUILD_NUMBER=65536", "CADRUMO_BUILD_NUMBER must be an integer from 1 to 65535"),
        ("CADRUMO_BUILD_NUMBER=0", "CADRUMO_BUILD_NUMBER must be an integer from 1 to 65535"),
        ("CADRUMO_BUILD_ID=20261019", "CADRUMO_BUILD_ID must be YYYYMMDD"),
        ("CADRUMO_BUILD_DATE=2026-10-19", "CADRUMO_BUILD_DATE must be an ISO UTC timestamp"),
    ],
)
def test_malformed_frozen_values_are_refused(tmp_path: Path, definition: str, refusal: str) -> None:
    result = run_command([_cmake(), f"-D{definition}", "-P", str(_script(tmp_path, tmp_path))], cwd=tmp_path)
    assert result.returncode != 0
    assert refusal in " ".join((result.stdout + result.stderr).split())


def test_reconfigure_drops_the_old_defaults_and_keeps_explicit_values(tmp_path: Path) -> None:
    ninja = shutil.which("ninja")
    assert ninja is not None, "Ninja is a build prerequisite; install it and put it on PATH"
    source = tmp_path / "source"
    source.mkdir()
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.0)\nproject(probe LANGUAGES NONE)\n"
        f'include("{BUILD_NUMBER}")\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/values.txt" "${CADRUMO_BUILD_NUMBER}|${CADRUMO_BUILD_DATE}")\n',
        encoding="utf-8",
    )
    build = tmp_path / "build"
    build.mkdir()
    # The cache a configure wrote before builds allocated their own identity.
    (build / "CMakeCache.txt").write_text(
        "//Explicit numeric build identifier\nCADRUMO_BUILD_NUMBER:STRING=1\n"
        "//Build date; SOURCE_DATE_EPOCH controls the default\nCADRUMO_BUILD_DATE:STRING=2026-10-13T18:44:20Z\n",
        encoding="utf-8",
    )
    configure = [_cmake(), "-S", str(source), "-B", str(build), "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja}"]
    result = run_command(configure, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (build / "values.txt").read_text(encoding="utf-8") == "|"
    result = run_command(
        [*configure, "-DCADRUMO_BUILD_NUMBER=1", "-DCADRUMO_BUILD_DATE=2026-10-19T08:00:00Z"], cwd=tmp_path
    )
    assert result.returncode == 0, result.stdout + result.stderr
    result = run_command(configure, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (build / "values.txt").read_text(encoding="utf-8") == "1|2026-10-19T08:00:00Z"
