"""Actual generator type controls supported CMake build configuration selection."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("profile", ["", "Unsupported", "Debug", "Release"])
def test_single_configuration_requires_supported_explicit_profile(tmp_path: Path, profile: str) -> None:
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(ConfigurationFixture LANGUAGES NONE)\n"
        f'include("{(REPO_ROOT / "native/cmake/Configurations.cmake").as_posix()}")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command(
        [cmake, "-G", "Ninja", "-S", str(tmp_path), "-B", str(tmp_path / "build"), f"-DCMAKE_BUILD_TYPE={profile}"],
        cwd=tmp_path,
    )
    if profile in {"Debug", "Release"}:
        assert result.returncode == 0, result.stderr
        cache = (tmp_path / "build/CMakeCache.txt").read_text(encoding="utf-8")
        assert "CMAKE_CONFIGURATION_TYPES:" not in cache
    else:
        assert result.returncode != 0
        assert "Select CMAKE_BUILD_TYPE=Debug or Release" in result.stderr


def test_multi_configuration_keeps_only_supported_profiles(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(ConfigurationFixture LANGUAGES NONE)\n"
        f'include("{(REPO_ROOT / "native/cmake/Configurations.cmake").as_posix()}")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command(
        [cmake, "-G", "Ninja Multi-Config", "-S", str(tmp_path), "-B", str(tmp_path / "build")], cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr
    assert "CMAKE_CONFIGURATION_TYPES:STRING=Debug;Release" in (tmp_path / "build/CMakeCache.txt").read_text(
        encoding="utf-8"
    )
