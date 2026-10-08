"""The managed builder cleans without Python and restores before individual targets run."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("external", [False, True])
def test_builder_cleanup_and_individual_rebuild(tmp_path: Path, external: bool) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    source = tmp_path / "source"
    source.mkdir()
    (source / "dev/packaging").mkdir(parents=True)
    (source / "dev/packaging/release-python-version").write_text(platform.python_version(), encoding="utf-8")
    for name in ("pyproject.toml", "uv.lock"):
        (source / name).touch()
    script = source / "fake_uv.py"
    script.write_text(
        "import os\nfrom pathlib import Path\n"
        "root = Path(os.environ['UV_PROJECT_ENVIRONMENT'])\n"
        "python = root / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')\n"
        "python.parent.mkdir(parents=True, exist_ok=True)\npython.write_text('managed builder')\n",
        encoding="utf-8",
    )
    fake_uv = source / ("uv.cmd" if os.name == "nt" else "uv")
    fake_uv.write_text(
        f'@"{sys.executable}" "{script}" %*\n'
        if os.name == "nt"
        else f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n',
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    external_setting = f'set(CADRUMO_DEV_PYTHON "{Path(sys.executable).as_posix()}")\n' if external else ""
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(BuilderCleanup LANGUAGES NONE)\n"
        'set(CADRUMO_SOURCE_ROOT "${CMAKE_SOURCE_DIR}")\n'
        f'set(CADRUMO_UV "{fake_uv.as_posix()}")\n{external_setting}'
        f'include("{(REPO_ROOT / "native/cmake/Bootstrap.cmake").as_posix()}")\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/check-builder.cmake" '
        '"if(NOT EXISTS \\"${CADRUMO_DEV_PYTHON}\\")\\nmessage(FATAL_ERROR \\"missing builder\\")\\nendif()\\n")\n'
        'add_custom_target(individual COMMAND "${CMAKE_COMMAND}" -P "${CMAKE_BINARY_DIR}/check-builder.cmake")\n'
        'add_custom_command(OUTPUT "${CMAKE_BINARY_DIR}/sibling" COMMAND "${CMAKE_COMMAND}" -E touch '
        '"${CMAKE_BINARY_DIR}/sibling")\nadd_custom_target(sibling_target DEPENDS "${CMAKE_BINARY_DIR}/sibling")\n',
        encoding="utf-8",
    )
    build = tmp_path / "build"

    def command(*arguments: str) -> str:
        result = run_command([cmake, *arguments], cwd=source)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    command("-G", "Ninja", "-S", str(source), "-B", str(build))
    command("--build", str(build), "--target", "individual", "sibling_target")
    sibling_time = (build / "sibling").stat().st_mtime_ns
    output = command("--build", str(build), "--target", "clean-setup-native-builder")
    assert not (build / "_deps/builder").exists()
    if external:
        assert "externally owned" in output
        assert Path(sys.executable).exists()
    command("--build", str(build), "--target", "individual", "sibling_target")
    assert (build / "sibling").stat().st_mtime_ns == sibling_time
    if not external:
        assert (build / "_deps/builder").exists()
