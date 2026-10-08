"""The source graph builds its payload before configuring the native package owner."""

from __future__ import annotations

import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_native_installer_preserves_configuration_and_clears_stale_desktop(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    source = tmp_path / "source with spaces"
    distribution = source / "native/cmake/distribution"
    distribution.mkdir(parents=True)
    (source / "native/CMakeLists.txt").write_text(
        'set(CADRUMO_MSI_ADAPTER "${PROJECT_BINARY_DIR}/adapter.dll")\n'
        'set(CADRUMO_MSI_RUNNER "${PROJECT_BINARY_DIR}/maintenance.exe")\n'
        'add_custom_target(rust_installer COMMAND "${CMAKE_COMMAND}" -E touch '
        '"${CADRUMO_MSI_ADAPTER}" "${CADRUMO_MSI_RUNNER}")\n',
        encoding="utf-8",
    )
    (distribution / "CMakePresets.json").write_text(
        json.dumps(
            {
                "version": 6,
                "configurePresets": [
                    {
                        "name": "native-fixture",
                        "generator": "Ninja Multi-Config",
                        "binaryDir": "${sourceDir}/../../../build/${presetName}",
                        "cacheVariables": {"CADRUMO_TARGET": "fixture"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (distribution / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(Distribution LANGUAGES NONE)\n"
        'if(NOT EXISTS "${CADRUMO_PAYLOAD}/ready")\nmessage(FATAL_ERROR "payload not built")\nendif()\n'
        'if(WIN32 AND (NOT EXISTS "${CADRUMO_MSI_ADAPTER}" OR NOT EXISTS "${CADRUMO_MSI_RUNNER}"))\n'
        'message(FATAL_ERROR "installer not built")\nendif()\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/consumed.txt" '
        '"${CADRUMO_PAYLOAD}\n${CADRUMO_DESKTOP_EXECUTABLE}\n${CADRUMO_CHANNEL}\n")\n'
        'add_custom_target(native-package COMMAND "${CMAKE_COMMAND}" -E touch '
        '"${CMAKE_BINARY_DIR}/packaged-$<CONFIG>")\n',
        encoding="utf-8",
    )
    module = (REPO_ROOT / "native/cmake/InstallerFlow.cmake").as_posix()
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(Source LANGUAGES NONE)\n"
        "set(CADRUMO_TARGET fixture)\nset(CADRUMO_CHANNEL preview)\n"
        'set(CADRUMO_PATH_STAGE "${PROJECT_BINARY_DIR}/stage")\n'
        "set(image_count 1)\n"
        'set(application_images "[{\\"desktop\\":true,\\"staged\\":${STAGED},'
        '\\"package_path\\":\\"desktop executable\\"}]")\n'
        "function(cadrumo_register_clean)\nendfunction()\n"
        "add_subdirectory(native)\n"
        'add_custom_target(bundle COMMAND "${CMAKE_COMMAND}" -E make_directory '
        '"${CADRUMO_PATH_STAGE}/$<CONFIG>/app" COMMAND "${CMAKE_COMMAND}" -E touch '
        '"${CADRUMO_PATH_STAGE}/$<CONFIG>/app/ready")\n'
        f'include("{module}")\n',
        encoding="utf-8",
    )
    binary = tmp_path / "source build"
    nested = source / "build/native-fixture"
    for staged, desktop in [("true", "desktop executable"), ("false", "")]:
        configured = run_command(
            [cmake, "-G", "Ninja Multi-Config", "-S", str(source), "-B", str(binary), f"-DSTAGED={staged}"],
            cwd=source,
        )
        assert configured.returncode == 0, configured.stderr
        built = run_command(
            [cmake, "--build", str(binary), "--config", "Release", "--target", "native-installer"], cwd=source
        )
        assert built.returncode == 0, built.stdout + built.stderr
        assert (nested / "consumed.txt").read_text().splitlines() == [
            (binary / "stage/Release/app").as_posix(),
            desktop,
            "preview",
        ]
        assert (nested / "packaged-Release").is_file()

    # Different source binary directories share the enrolled distribution owner.
    # Its configured payload must not change halfway through the first package.
    (distribution / "check.cmake").write_text(
        'file(WRITE "${BINARY}/entered" "ready")\n'
        'execute_process(COMMAND "${CMAKE_COMMAND}" -E sleep 1)\n'
        'file(STRINGS "${BINARY}/consumed.txt" observed LIMIT_COUNT 1)\n'
        'if(NOT observed STREQUAL EXPECTED)\nmessage(FATAL_ERROR "payload changed during package")\nendif()\n',
        encoding="utf-8",
    )
    with (distribution / "CMakeLists.txt").open("a", encoding="utf-8") as output:
        output.write(
            'add_custom_command(TARGET native-package POST_BUILD COMMAND "${CMAKE_COMMAND}" '
            '"-DBINARY=${CMAKE_BINARY_DIR}" "-DEXPECTED=${CADRUMO_PAYLOAD}" '
            '-P "${CMAKE_SOURCE_DIR}/check.cmake" VERBATIM)\n'
        )
    other_binary = tmp_path / "other source build"
    configured = run_command(
        [cmake, "-G", "Ninja Multi-Config", "-S", str(source), "-B", str(other_binary), "-DSTAGED=false"],
        cwd=source,
    )
    assert configured.returncode == 0, configured.stderr

    def build(directory: Path) -> None:
        result = run_command(
            [cmake, "--build", str(directory), "--config", "Release", "--target", "native-installer"], cwd=source
        )
        assert result.returncode == 0, result.stdout + result.stderr

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(build, binary)
        deadline = time.monotonic() + 30
        while not (nested / "entered").exists():
            if first.done():
                first.result()
                pytest.fail("native package did not start")
            assert time.monotonic() < deadline, "native package did not start within its fixture bound"
            time.sleep(0.01)
        second = executor.submit(build, other_binary)
        first.result(timeout=30)
        second.result(timeout=30)
    assert (nested / "consumed.txt").read_text().splitlines()[0] == (other_binary / "stage/Release/app").as_posix()
