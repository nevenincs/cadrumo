"""Compiler/wrapper/SDK content changes cannot reuse configured product inputs."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..action_cache import completed, current, fingerprint
from ..build_toolchain import builder_inputs, sysroot_inventory, write_sysroot_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_configured_toolchain_and_sdk_content_drive_cache_admission(tmp_path: Path) -> None:
    compiler = tmp_path / "compiler"
    wrapper = tmp_path / "linker-wrapper"
    toolchain = tmp_path / "toolchain.cmake"
    sysroot = tmp_path / "sdk"
    sysroot.mkdir()
    header = sysroot / "target.h"
    for path in (compiler, wrapper, toolchain, header):
        path.write_text(f"selected {path.name}", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    output = project / "build-toolchain.json"
    (project / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(BuilderIdentity LANGUAGES NONE)\n"
        'set(build_toolchain "{}")\n'
        f'set(CADRUMO_DEV_PYTHON "{Path(sys.executable).as_posix()}")\n'
        f'set(CMAKE_C_COMPILER "{compiler.as_posix()}")\n'
        f'set(CMAKE_TOOLCHAIN_FILE "{toolchain.as_posix()}")\n'
        f'set(CADRUMO_RUST_LINKER "{wrapper.as_posix()}")\n'
        f'set(CMAKE_SYSROOT "{sysroot.as_posix()}")\n'
        f'include("{(REPO_ROOT / "native/cmake/ToolchainIdentity.cmake").as_posix()}")\n'
        f'file(WRITE "{output.as_posix()}" "${{build_toolchain}}")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None

    def configure() -> dict[str, Any]:
        result = run_command([cmake, "-S", str(project), "-B", str(tmp_path / "cmake")], cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        observed = json.loads(output.read_text(encoding="utf-8"))
        assert isinstance(observed, dict)
        return observed

    selected = configure()
    paths = builder_inputs(selected)
    assert {path.resolve() for path in (compiler, wrapper, toolchain, header)} <= {path.resolve() for path in paths}
    assert len(selected["builder_files"]) == 3
    assert selected["sysroots"]["CMAKE_SYSROOT"]["files"] == 1
    inputs = tmp_path / "inputs.txt"
    inputs.write_text(str(output) + "\n", encoding="utf-8")
    baseline = fingerprint(inputs, paths)
    destination = tmp_path / "runtime"
    destination.mkdir()
    (destination / "payload").write_bytes(b"complete")
    completed(destination, baseline)
    assert current(destination, baseline)
    wrapper.write_text("substituted linker wrapper", encoding="utf-8")
    with pytest.raises(ValueError, match="CADRUMO_RUST_LINKER; reconfigure"):
        builder_inputs(selected)
    refreshed = configure()
    assert not current(destination, fingerprint(inputs, builder_inputs(refreshed)))
    header.write_text("changed SDK ABI", encoding="utf-8")
    with pytest.raises(ValueError, match="CMAKE_SYSROOT resources changed; reconfigure"):
        builder_inputs(refreshed)


def test_sdk_sidecar_contains_contained_links_and_refuses_escape_or_cycle(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    include = sdk / "include"
    include.mkdir(parents=True)
    (include / "target.h").write_bytes(b"public SDK ABI")
    alias = sdk / "headers"
    try:
        alias.symlink_to(include, target_is_directory=True)
    except OSError:
        pytest.skip("The runner cannot create a directory symlink")
    inventory = sysroot_inventory(sdk)
    assert inventory["links"]["headers"]["target"] == "include"
    assert inventory["links"]["headers"]["kind"] == "directory"
    assert list(inventory["files"]) == ["include/target.h"]
    sidecar = write_sysroot_inventory(sdk, tmp_path / "evidence/sdk.json")
    assert sidecar["files"] == 1
    assert "public SDK ABI" not in Path(sidecar["inventory"]).read_text(encoding="utf-8")
    alias.unlink()
    alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes the selected SDK"):
        sysroot_inventory(sdk)
    alias.unlink()
    alias.symlink_to(sdk, target_is_directory=True)
    with pytest.raises(ValueError, match="directory link cycle"):
        sysroot_inventory(sdk)


def test_selected_sdk_retains_ancestor_alias_and_detects_header_changes(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    headers = sdk / "framework" / "Headers"
    headers.mkdir(parents=True)
    header = headers / "api.h"
    header.write_bytes(b"original native API")
    alias = headers / "framework"
    try:
        alias.symlink_to(headers, target_is_directory=True)
    except OSError:
        pytest.skip("The runner cannot create SDK directory aliases")
    sidecar = write_sysroot_inventory(sdk, tmp_path / "evidence/sdk.json")
    selected = {"sysroots": {"CMAKE_SYSROOT": sidecar}}
    evidence = json.loads(Path(sidecar["inventory"]).read_text(encoding="utf-8"))
    assert evidence["links"]["framework/Headers/framework"]["target"] == "framework/Headers"
    assert list(evidence["files"]) == ["framework/Headers/api.h"]
    assert header in builder_inputs(selected)
    header.write_bytes(b"changed native API")
    with pytest.raises(ValueError, match="resources changed; reconfigure"):
        builder_inputs(selected)
    header.write_bytes(b"original native API")
    alias.unlink()
    alias.symlink_to(sdk, target_is_directory=True)
    with pytest.raises(ValueError, match="resources changed; reconfigure"):
        builder_inputs(selected)


def test_compiler_alias_retarget_cannot_admit_the_previous_resolved_file(tmp_path: Path) -> None:
    first = tmp_path / "compiler-one"
    second = tmp_path / "compiler-two"
    first.write_bytes(b"same compiler bytes")
    second.write_bytes(first.read_bytes())
    alias = tmp_path / "cc"
    try:
        alias.symlink_to(first)
    except OSError:
        pytest.skip("The runner cannot create compiler symlinks")
    project = tmp_path / "project"
    project.mkdir()
    output = project / "toolchain.json"
    (project / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(CompilerAlias LANGUAGES NONE)\n"
        'set(build_toolchain "{}")\n'
        f'set(CMAKE_C_COMPILER "{alias.as_posix()}")\n'
        f'include("{(REPO_ROOT / "native/cmake/ToolchainIdentity.cmake").as_posix()}")\n'
        f'file(WRITE "{output.as_posix()}" "${{build_toolchain}}")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, "-S", str(project), "-B", str(tmp_path / "build")], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    selected = json.loads(output.read_text(encoding="utf-8"))
    record = selected["builder_files"]["CMAKE_C_COMPILER"]
    assert Path(record["path"]) == alias
    assert Path(record["resolved"]) == first.resolve()
    assert builder_inputs(selected) == (alias,)
    alias.unlink()
    alias.symlink_to(second)
    with pytest.raises(ValueError, match="resolution changed: CMAKE_C_COMPILER"):
        builder_inputs(selected)
