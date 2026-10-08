"""Target cleanup preserves sibling outputs and refuses paths outside build ownership."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..cleanup import clean, clean_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _manifest(build: Path, source: Path, paths: list[str]) -> None:
    build.mkdir(exist_ok=True)
    (build / "CMakeCache.txt").write_text(f"CMAKE_HOME_DIRECTORY:INTERNAL={source.as_posix()}\n", encoding="utf-8")
    (build / "cleanup-Debug.json").write_text(
        json.dumps({"source": str(source), "targets": {"one": {"paths": paths, "depends": []}}}), encoding="utf-8"
    )


def test_cleanup_validates_every_path_before_deleting_anything(tmp_path: Path) -> None:
    build = tmp_path / "build"
    source = tmp_path / "source"
    source.mkdir()
    _manifest(build, source, [str(build / "valid"), str(tmp_path / "outside")])
    (build / "valid").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="escapes binary directory"):
        clean_target(build, "one", "Debug")
    assert (build / "valid").read_text(encoding="utf-8") == "keep"


def test_cleanup_rejects_linked_directory(tmp_path: Path) -> None:
    build = tmp_path / "build"
    source = tmp_path / "source"
    source.mkdir()
    _manifest(build, source, [str(build / "linked" / "file")])
    (source / "file").write_text("keep", encoding="utf-8")
    try:
        (build / "linked").symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit symlink creation")
    with pytest.raises(ValueError, match="Linked cleanup path"):
        clean_target(build, "one", "Debug")
    assert (source / "file").exists()


def test_clean_all_includes_all_configured_target_outputs_but_preserves_identity(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    build = tmp_path / "build"
    _manifest(build, source, [str(build / "objects/Debug/one.obj"), str(build / "generated/contract.h")])
    release = json.loads((build / "cleanup-Debug.json").read_text(encoding="utf-8"))
    release["targets"]["one"]["paths"] = [str(build / "objects/Release/one.obj")]
    (build / "cleanup-Release.json").write_text(json.dumps(release), encoding="utf-8")
    (build / "build-paths.json").write_text(
        json.dumps({"source": str(source), "paths": {"stage": "stage"}, "cleanup": {"stage": ["stage"]}}),
        encoding="utf-8",
    )
    outputs = ["objects/Debug/one.obj", "objects/Release/one.obj", "generated/contract.h", "stage/app.exe"]
    for name in [*outputs, "generated/identity.json", "_deps/builder/python.exe"]:
        path = build / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("owned", encoding="utf-8")
    clean(build, "all")
    assert all(not (build / name).exists() for name in outputs)
    assert (build / "generated/identity.json").exists()
    assert (build / "_deps/builder/python.exe").exists()


def test_object_file_list_is_enrolled_without_generator_metadata(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    build = tmp_path / "build"
    module = (REPO_ROOT / "native/cmake/Cleanup.cmake").as_posix()
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(ObjectCleanup LANGUAGES NONE)\n"
        f'include("{module}")\n'
        "add_library(objects OBJECT IMPORTED GLOBAL)\n"
        "set_property(TARGET objects PROPERTY IMPORTED_OBJECTS "
        '"${CMAKE_BINARY_DIR}/one.obj;${CMAKE_BINARY_DIR}/two.obj")\n'
        'cadrumo_register_clean(TARGET one PATHS "$<TARGET_OBJECTS:objects>")\n'
        "add_custom_target(one)\ncadrumo_finalize_clean_targets()\n",
        encoding="utf-8",
    )
    result = run_command([cmake, "-G", "Ninja", "-S", str(tmp_path), "-B", str(build)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout
    document = json.loads((build / "cleanup-.json").read_text(encoding="utf-8"))
    assert document["targets"]["one"]["paths"] == [(build / name).as_posix() for name in ("one.obj", "two.obj")]


@pytest.mark.parametrize("generator", ["Ninja", "Ninja Multi-Config"])
def test_individual_clean_rebuild_preserves_sibling_and_configuration(tmp_path: Path, generator: str) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    source = tmp_path / "source"
    source.mkdir()
    build = tmp_path / "build"
    module = (REPO_ROOT / "native/cmake/Cleanup.cmake").as_posix()
    (source / "input.txt").write_text("fixture", encoding="utf-8")
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(CleanupFixture LANGUAGES NONE)\n"
        f'include("{module}")\nset(CADRUMO_DEV_PYTHON "{Path(sys.executable).as_posix()}")\n'
        "foreach(name IN ITEMS one two)\n"
        ' set(output "${CMAKE_BINARY_DIR}/$<CONFIG>/${name}.txt")\n'
        ' add_custom_command(OUTPUT "${output}" COMMAND "${CMAKE_COMMAND}" -E make_directory '
        '"${CMAKE_BINARY_DIR}/$<CONFIG>" COMMAND "${CMAKE_COMMAND}" -E copy '
        '"${CMAKE_SOURCE_DIR}/input.txt" "${output}" DEPENDS "${CMAKE_SOURCE_DIR}/input.txt")\n'
        ' add_custom_target(${name} ALL DEPENDS "${output}")\n'
        ' cadrumo_register_clean(TARGET ${name} PATHS "${output}")\n'
        "endforeach()\ncadrumo_finalize_clean_targets()\n",
        encoding="utf-8",
    )

    def command(*arguments: str) -> None:
        result = run_command([cmake, *arguments], cwd=source)
        assert result.returncode == 0, result.stderr + result.stdout

    command("-G", generator, "-S", str(source), "-B", str(build), "-DCMAKE_BUILD_TYPE=Debug")
    command("--build", str(build), "--config", "Debug")
    sibling = build / "Debug/two.txt"
    sibling_time = sibling.stat().st_mtime_ns
    release_time = None
    if generator == "Ninja Multi-Config":
        command("--build", str(build), "--config", "Release")
        release_time = (build / "Release/one.txt").stat().st_mtime_ns
    command("--build", str(build), "--config", "Debug", "--target", "clean-one")
    assert not (build / "Debug/one.txt").exists()
    assert sibling.stat().st_mtime_ns == sibling_time
    command("--build", str(build), "--config", "Debug")
    assert (build / "Debug/one.txt").read_text(encoding="utf-8") == "fixture"
    assert sibling.stat().st_mtime_ns == sibling_time
    if release_time is not None:
        assert (build / "Release/one.txt").stat().st_mtime_ns == release_time
    command("--build", str(build), "--config", "Debug", "--target", "clean")
    assert not (build / "Debug/one.txt").exists()
    command("--build", str(build), "--config", "Debug")
    assert (build / "Debug/two.txt").exists()
