"""Native CTest processes inherit build-owned temporary and storage roots."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

MODULE = REPO_ROOT / "native/cmake/CTestEnvironment.cmake"


def _clean_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("CADRUMO_STORAGE_ROOT", None)
    return environment


def test_ctest_environment_reaches_nested_tests_and_preserves_custom_roots(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    ctest = shutil.which("ctest")
    assert cmake is not None and ctest is not None

    source = tmp_path / "source"
    binary = tmp_path / "build"
    child = source / "child"
    nested = child / "nested"
    nested.mkdir(parents=True)
    module = source / "CTestEnvironment.cmake"
    shutil.copyfile(MODULE, module)

    (source / "verify.cmake").write_text(
        "foreach(name IN ITEMS TEMP TMP TMPDIR)\n"
        '  if(NOT "$ENV{${name}}" STREQUAL "${EXPECT_${name}}")\n'
        "    message(FATAL_ERROR \"${name} was not pinned: '$ENV{${name}}'\")\n"
        "  endif()\n"
        "endforeach()\n"
        "foreach(name IN ITEMS CADRUMO_TEST_LOG_ROOT CADRUMO_SCRATCH_BASE CADRUMO_DEV_CACHE_ROOT)\n"
        '  if(NOT "$ENV{${name}}" STREQUAL "${EXPECT_${name}}")\n'
        "    message(FATAL_ERROR \"${name} was not pinned: '$ENV{${name}}'\")\n"
        "  endif()\n"
        "endforeach()\n"
        'if(NOT "$ENV{CADRUMO_STORAGE_ROOT}" STREQUAL "${EXPECT_STORAGE}")\n'
        "  message(FATAL_ERROR \"CADRUMO_STORAGE_ROOT was not the expected root: '$ENV{CADRUMO_STORAGE_ROOT}'\")\n"
        "endif()\n"
        # A retired storage variable is never added to a test's environment.
        "if(DEFINED ENV{CADRUMO_LOCAL_STORAGE_ROOT} OR DEFINED ENV{CADRUMO_TEMP_DIR})\n"
        '  message(FATAL_ERROR "a retired storage variable was added")\n'
        "endif()\n",
        encoding="utf-8",
    )

    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.28)\n"
        "project(ctest_environment_probe NONE)\n"
        "enable_testing()\n"
        'set(CADRUMO_CTEST_TEMPORARY "${CMAKE_BINARY_DIR}/ctest-temp")\n'
        'set(CADRUMO_PATH_TESTING "${CMAKE_BINARY_DIR}/testing")\n'
        "include(CTestEnvironment.cmake)\n"
        'add_test(NAME root.test COMMAND "${CMAKE_COMMAND}"\n'
        '  "-DEXPECT_TEMP=${CADRUMO_CTEST_TEMPORARY}"\n'
        '  "-DEXPECT_CADRUMO_TEST_LOG_ROOT=${CADRUMO_PATH_TESTING}/Debug/test-logs"\n'
        '  "-DEXPECT_CADRUMO_SCRATCH_BASE=${CADRUMO_PATH_TESTING}/Debug/scratch"\n'
        '  "-DEXPECT_CADRUMO_DEV_CACHE_ROOT=${CADRUMO_PATH_TESTING}/Debug/cache"\n'
        '  "-DEXPECT_TMP=${CADRUMO_CTEST_TEMPORARY}"\n'
        '  "-DEXPECT_TMPDIR=${CADRUMO_CTEST_TEMPORARY}"\n'
        '  "-DEXPECT_STORAGE=${CADRUMO_PATH_TESTING}/Debug/storage"\n'
        '  -P "${CMAKE_CURRENT_SOURCE_DIR}/verify.cmake")\n'
        "add_subdirectory(child)\n"
        'cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL cadrumo_finalize_ctest_environment)\n',
        encoding="utf-8",
    )
    (child / "CMakeLists.txt").write_text(
        'add_test(NAME child.test COMMAND "${CMAKE_COMMAND}"\n'
        '  "-DEXPECT_TEMP=${CMAKE_BINARY_DIR}/custom-temp"\n'
        '  "-DEXPECT_CADRUMO_TEST_LOG_ROOT=${CMAKE_BINARY_DIR}/testing/Debug/test-logs"\n'
        '  "-DEXPECT_CADRUMO_SCRATCH_BASE=${CMAKE_BINARY_DIR}/testing/Debug/scratch"\n'
        '  "-DEXPECT_CADRUMO_DEV_CACHE_ROOT=${CMAKE_BINARY_DIR}/testing/Debug/cache"\n'
        '  "-DEXPECT_TMP=${CMAKE_BINARY_DIR}/ctest-temp"\n'
        '  "-DEXPECT_TMPDIR=${CMAKE_BINARY_DIR}/ctest-temp"\n'
        '  "-DEXPECT_STORAGE=${CMAKE_BINARY_DIR}/testing/Debug/storage"\n'
        '  -P "${CMAKE_SOURCE_DIR}/verify.cmake")\n'
        "set_tests_properties(child.test PROPERTIES ENVIRONMENT\n"
        '  "TEMP=${CMAKE_BINARY_DIR}/custom-temp")\n'
        "add_subdirectory(nested)\n",
        encoding="utf-8",
    )
    (nested / "CMakeLists.txt").write_text(
        'add_test(NAME nested.test COMMAND "${CMAKE_COMMAND}"\n'
        '  "-DEXPECT_TEMP=${CMAKE_BINARY_DIR}/ctest-temp"\n'
        '  "-DEXPECT_CADRUMO_TEST_LOG_ROOT=${CMAKE_BINARY_DIR}/testing/Debug/test-logs"\n'
        '  "-DEXPECT_CADRUMO_SCRATCH_BASE=${CMAKE_BINARY_DIR}/testing/Debug/scratch"\n'
        '  "-DEXPECT_CADRUMO_DEV_CACHE_ROOT=${CMAKE_BINARY_DIR}/testing/Debug/cache"\n'
        '  "-DEXPECT_TMP=${CMAKE_BINARY_DIR}/ctest-temp"\n'
        '  "-DEXPECT_TMPDIR=${CMAKE_BINARY_DIR}/ctest-temp"\n'
        '  "-DEXPECT_STORAGE=${CMAKE_BINARY_DIR}/nested-storage"\n'
        '  -P "${CMAKE_SOURCE_DIR}/verify.cmake")\n'
        "set_tests_properties(nested.test PROPERTIES ENVIRONMENT\n"
        '  "CADRUMO_STORAGE_ROOT=${CMAKE_BINARY_DIR}/nested-storage")\n',
        encoding="utf-8",
    )

    environment = _clean_environment()
    configured = run_command(
        [cmake, "-S", str(source), "-B", str(binary), "-DCMAKE_BUILD_TYPE=Debug"],
        cwd=source,
        environment=environment,
    )
    assert configured.returncode == 0, configured.stderr
    tested = run_command(
        [ctest, "--test-dir", str(binary), "-C", "Debug", "--output-on-failure"],
        cwd=source,
        environment=environment,
    )
    assert tested.returncode == 0, tested.stdout + tested.stderr
