"""A project configures only into the binary directory one of its presets names."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

GUARD = REPO_ROOT / "native/cmake/BinaryDirectory.cmake"
PROJECTS = (
    REPO_ROOT / "CMakePresets.json",
    REPO_ROOT / "native/desktop/CMakePresets.json",
    REPO_ROOT / "native/cmake/distribution/CMakePresets.json",
)


def _check(directory: Path, binary: Path, presets: Path, root: Path):
    cmake = shutil.which("cmake")
    assert cmake is not None
    script = directory / "binary-directory.cmake"
    arguments = " ".join(f'"{path.as_posix()}"' for path in (binary, presets, root))
    script.write_text(
        f'include("{GUARD.as_posix()}")\ncadrumo_require_enrolled_binary_directory({arguments})\n',
        encoding="utf-8",
    )
    return run_command([cmake, "-P", str(script)], cwd=directory)


def _check_build_paths(directory: Path, binary: Path, source: Path):
    cmake = shutil.which("cmake")
    assert cmake is not None
    module = source / "native/cmake/BuildPaths.cmake"
    script = directory / "build-paths.cmake"
    script.write_text(
        f'set(CMAKE_SOURCE_DIR "{source.as_posix()}")\n'
        f'set(CMAKE_BINARY_DIR "{binary.as_posix()}")\n'
        f'include("{module.as_posix()}")\n',
        encoding="utf-8",
    )
    return run_command([cmake, "-P", str(script)], cwd=directory)


def _presets(directory: Path, *names: str, hidden: tuple[str, ...] = ()) -> Path:
    path = directory / "CMakePresets.json"
    members = [{"name": name} for name in names] + [{"name": name, "hidden": True} for name in hidden]
    path.write_text(json.dumps({"version": 6, "configurePresets": members}), encoding="utf-8")
    return path


def _directory_redirect(link: Path, target: Path) -> None:
    if os.name == "nt":
        # A junction does not require the symbolic-link privilege on Windows.
        command = os.environ.get("COMSPEC", "cmd.exe")
        result = run_command(
            [command, "/d", "/c", "mklink", "/J", str(link), str(target)],
            cwd=link.parent,
        )
        if result.returncode != 0:
            pytest.skip(f"could not create a temporary directory junction: {result.stderr}")
        return
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"could not create a temporary directory symlink: {error}")


def test_enrolled_directory_is_admitted(tmp_path: Path) -> None:
    presets = _presets(tmp_path, "windows-x64", "linux-x86-64")
    result = _check(tmp_path, tmp_path / "build" / "linux-x86-64", presets, tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("linked_component", ["build", "preset"])
def test_enrolled_directory_redirects_are_refused(tmp_path: Path, linked_component: str) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    presets = _presets(repository, "windows-x64")
    external = tmp_path / "external"
    external.mkdir()
    binary_root = repository / "build"
    if linked_component == "build":
        _directory_redirect(binary_root, external)
    else:
        binary_root.mkdir()
        _directory_redirect(binary_root / "windows-x64", external)

    result = _check(
        tmp_path,
        binary_root / "windows-x64",
        presets,
        repository,
    )
    assert result.returncode != 0
    assert "symlink or junction in the build path is not allowed" in result.stderr


def test_root_spelled_through_parent_segments_is_the_same_root(tmp_path: Path) -> None:
    presets = _presets(tmp_path, "windows-x64")
    nested = tmp_path / "native" / "cmake"
    nested.mkdir(parents=True)
    result = _check(tmp_path, tmp_path / "build" / "windows-x64", presets, nested / ".." / "..")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("leaf", ["e2e-final", "smoke-probe", "d2-desktop", "windows-x64-2", "Windows-X64"])
def test_unenrolled_name_is_refused(tmp_path: Path, leaf: str) -> None:
    presets = _presets(tmp_path, "windows-x64")
    result = _check(tmp_path, tmp_path / "build" / leaf, presets, tmp_path)
    assert result.returncode != 0
    assert "is not an enrolled binary directory" in result.stderr
    assert "windows-x64" in result.stderr


@pytest.mark.parametrize("parent", ["", "out", "build/nested"])
def test_enrolled_name_outside_the_build_root_is_refused(tmp_path: Path, parent: str) -> None:
    presets = _presets(tmp_path, "windows-x64")
    result = _check(tmp_path, tmp_path / parent / "windows-x64", presets, tmp_path)
    assert result.returncode != 0
    assert "is not an enrolled binary directory" in result.stderr


def test_hidden_preset_enrols_nothing(tmp_path: Path) -> None:
    presets = _presets(tmp_path, "windows-x64", hidden=("base",))
    result = _check(tmp_path, tmp_path / "build" / "base", presets, tmp_path)
    assert result.returncode != 0


def test_project_without_presets_is_refused(tmp_path: Path) -> None:
    result = _check(tmp_path, tmp_path / "build" / "windows-x64", tmp_path / "CMakePresets.json", tmp_path)
    assert result.returncode != 0
    assert "enrols no binary directory" in result.stderr


@pytest.mark.parametrize("linked_output", ["generated", "temporary"])
def test_declared_build_outputs_reject_symlinks_before_writing_manifest(tmp_path: Path, linked_output: str) -> None:
    source = tmp_path / "repository"
    cmake_directory = source / "native/cmake"
    cmake_directory.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / "native/cmake/BuildPaths.cmake", cmake_directory / "BuildPaths.cmake")
    shutil.copyfile(REPO_ROOT / "native/cmake/BinaryDirectory.cmake", cmake_directory / "BinaryDirectory.cmake")
    _presets(source, "test-build")
    binary = source / "build/test-build"
    binary.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    _directory_redirect(binary / linked_output, external)

    result = _check_build_paths(tmp_path, binary, source)
    assert result.returncode != 0
    assert "symlink or junction" in result.stderr
    assert not (binary / "build-paths.json").exists()


@pytest.mark.parametrize("presets", PROJECTS, ids=lambda path: path.parent.name)
def test_each_project_admits_exactly_its_own_presets(tmp_path: Path, presets: Path) -> None:
    names = [member["name"] for member in json.loads(presets.read_text(encoding="utf-8"))["configurePresets"]]
    assert names
    for name in names:
        result = _check(tmp_path, REPO_ROOT / "build" / name, presets, REPO_ROOT)
        assert result.returncode == 0, result.stderr
    others = {
        member["name"]
        for other in PROJECTS
        if other != presets
        for member in json.loads(other.read_text(encoding="utf-8"))["configurePresets"]
    }
    for name in sorted(others):
        assert _check(tmp_path, REPO_ROOT / "build" / name, presets, REPO_ROOT).returncode != 0
