"""Explicit native Darwin toolchain admission; portable refusals are not compiler proof."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ...runtime_wheelhouse_contract import target_platform

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
TOOLCHAIN = REPO_ROOT / "native/cmake/DarwinToolchain.cmake"


def _cmake() -> str:
    executable = shutil.which("cmake")
    assert executable is not None
    return executable


def _admit(tmp_path: Path, assignments: dict[str, str]) -> str:
    script = tmp_path / "admit.cmake"
    script.write_text(
        "\n".join(f"set({key} [[{value}]])" for key, value in assignments.items())
        + f'\ninclude("{TOOLCHAIN.as_posix()}")\n',
        encoding="utf-8",
    )
    result = run_command([_cmake(), "-P", str(script)], cwd=tmp_path)
    assert result.returncode != 0
    return result.stderr


def test_wrong_native_host_and_missing_reviewed_inputs_refuse(tmp_path: Path) -> None:
    assert "native arm64 Mac" in _admit(tmp_path, {"CMAKE_HOST_SYSTEM_NAME": "Linux"})
    host = {"CMAKE_HOST_SYSTEM_NAME": "Darwin", "CMAKE_HOST_SYSTEM_PROCESSOR": "arm64"}
    assert "Supply reviewed CADRUMO_DARWIN_COMPILER" in _admit(tmp_path, host)
    assert "cross compilation" in _admit(tmp_path, host | {"CMAKE_CROSSCOMPILING": "TRUE"})


@pytest.mark.parametrize(
    ("version", "canonical", "expected"),
    [
        ("26.4", "macosx26.4", "reviewed macOS SDK"),
        ("26.5", "iphoneos26.5", "reviewed macOS SDK"),
        ("26.5", "macosx26.5", "reviewed Apple clang"),
    ],
)
def test_sdk_identity_and_non_apple_compiler_refuse(
    tmp_path: Path, version: str, canonical: str, expected: str
) -> None:
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    (sdk / "SDKSettings.json").write_text(
        json.dumps({"Version": version, "CanonicalName": canonical}), encoding="utf-8"
    )
    assignments = {
        "CMAKE_HOST_SYSTEM_NAME": "Darwin",
        "CMAKE_HOST_SYSTEM_PROCESSOR": "arm64",
        # CMake is deliberately a real, incompatible executable: no compiler is faked.
        "CADRUMO_DARWIN_COMPILER": Path(_cmake()).as_posix(),
        "CADRUMO_DARWIN_COMPILER_IDENTITY": "Apple clang version reviewed",
        "CADRUMO_DARWIN_SDK_ROOT": sdk.as_posix(),
        "CADRUMO_DARWIN_SDK_VERSION": "26.5",
    }
    assert expected in _admit(tmp_path, assignments)


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual native Darwin compiler and SDK required")
def test_reviewed_native_toolchain_builds_and_rejects_changed_inputs(tmp_path: Path) -> None:
    names = ("COMPILER", "COMPILER_IDENTITY", "SDK_ROOT", "SDK_VERSION")
    inputs = {f"CADRUMO_DARWIN_{name}": os.environ.get(f"CADRUMO_DARWIN_{name}", "") for name in names}
    if not all(inputs.values()):
        pytest.skip("Supply explicit reviewed Darwin toolchain inputs")
    project = tmp_path / "project"
    project.mkdir()
    (project / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(DarwinAdmission LANGUAGES C)\nadd_executable(probe main.c)\n",
        encoding="utf-8",
    )
    (project / "main.c").write_text(
        "#include <AvailabilityMacros.h>\n"
        "#if !defined(__APPLE__) || !defined(__aarch64__)\n#error Wrong target\n#endif\n"
        "int main(void) { return MAC_OS_X_VERSION_MIN_REQUIRED == 140000 ? 0 : 1; }\n",
        encoding="utf-8",
    )
    build = tmp_path / "build"
    floor = target_platform("macos-arm64").floor.removeprefix("macos-")
    command = [
        _cmake(),
        "-S",
        str(project),
        "-B",
        str(build),
        "-G",
        "Ninja",
        f"-DCMAKE_TOOLCHAIN_FILE={TOOLCHAIN}",
        "-DCMAKE_C_COMPILER:FILEPATH=",
        "-DCMAKE_OSX_SYSROOT:PATH=",
        "-DCMAKE_OSX_ARCHITECTURES=arm64",
        f"-DCMAKE_OSX_DEPLOYMENT_TARGET={floor}",
    ]
    command.extend(f"-D{key}={value}" for key, value in inputs.items())
    result = run_command(command, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    cache = {
        line.split(":", 1)[0]: line.split("=", 1)[1]
        for line in (build / "CMakeCache.txt").read_text(encoding="utf-8").splitlines()
        if line.startswith(("CMAKE_C_COMPILER:", "CMAKE_OSX_SYSROOT:"))
    }
    assert cache["CMAKE_C_COMPILER"] == inputs["CADRUMO_DARWIN_COMPILER"]
    assert cache["CMAKE_OSX_SYSROOT"] == inputs["CADRUMO_DARWIN_SDK_ROOT"]
    result = run_command([_cmake(), "--build", str(build)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert run_command([str(build / "probe")], cwd=tmp_path).returncode == 0
    result = run_command([*command, "-DCADRUMO_DARWIN_SDK_VERSION=0.0"], cwd=tmp_path)
    assert result.returncode != 0 and "reviewed macOS SDK" in result.stderr
    result = run_command([*command, "-DCMAKE_C_COMPILER=/usr/bin/false"], cwd=tmp_path)
    assert result.returncode != 0 and "differs from the reviewed Darwin" in result.stderr
    result = run_command(
        [*command, "-DCMAKE_C_COMPILER=" + inputs["CADRUMO_DARWIN_COMPILER"], "-DCMAKE_OSX_SYSROOT=/invalid"],
        cwd=tmp_path,
    )
    assert result.returncode != 0 and "CMAKE_OSX_SYSROOT differs" in result.stderr
