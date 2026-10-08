"""The desktop host receives admitted Rust tools despite a poisoned ambient Cargo."""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from ..build_toolchain import builder_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _rust() -> tuple[Path, str, str]:
    targets = {
        ("win32", "AMD64"): "windows-x86-64",
        ("linux", "x86_64"): "linux-x86-64",
        ("linux", "aarch64"): "linux-aarch64",
        ("darwin", "arm64"): "macos-arm64",
    }
    target = targets.get((sys.platform, platform.machine()))
    if target is None:
        pytest.skip("This runner has no enrolled native desktop Rust target")
    pins = json.loads((REPO_ROOT / "native/toolchain.json").read_text(encoding="utf-8"))
    version = pins["rust"]
    triple = pins["targets"][target]["rust_target"]
    assert isinstance(version, str) and isinstance(triple, str)
    root = Path.home() / ".rustup/toolchains" / (version + "-" + triple)
    suffix = ".exe" if sys.platform == "win32" else ""
    if not (root / "bin" / ("cargo" + suffix)).is_file():
        pytest.skip("The selected native desktop Rust toolchain is unavailable on this runner")
    return root, triple, suffix


def _fixture(tmp_path: Path, *, selected_target: str | None = None) -> tuple[Path, Path, Path]:
    root, triple, suffix = _rust()
    node = shutil.which("node")
    assert node is not None
    source = tmp_path / "source"
    (source / "native").mkdir(parents=True)
    (source / "native/CMakeLists.txt").write_text(
        'set(CADRUMO_RUST_ENVIRONMENT_NAMES LIB)\nset(CADRUMO_RUST_ENV_LIB "first;second")\n'
        "add_custom_target(rust_platform)\n",
        encoding="utf-8",
    )
    result = tmp_path / "result.json"
    probe = source / "probe.mjs"
    probe.write_text(
        """import {spawnSync} from "node:child_process";
import {delimiter} from "node:path";
import {writeFileSync} from "node:fs";
process.env.PATH = process.env.CADRUMO_DESKTOP_RUST_BIN + delimiter + process.env.PATH;
const result = spawnSync("cargo", ["--version"], {encoding: "utf8", windowsHide: true});
if (result.error) throw result.error;
if (result.status !== 0) throw new Error(result.stderr);
writeFileSync(process.argv[2], JSON.stringify({
  cargo: result.stdout.trim(), rustc: process.env.RUSTC, rustdoc: process.env.RUSTDOC,
  lib: process.env.LIB, target: process.env.CARGO_BUILD_TARGET ?? null
}));
""",
        encoding="utf-8",
    )
    (source / "CMakeLists.txt").write_text(
        f'''cmake_minimum_required(VERSION 4.4)
project(DesktopRustProbe LANGUAGES NONE)
set(CMAKE_EXECUTABLE_SUFFIX "{suffix}")
set(CADRUMO_SOURCE_ROOT "{source.as_posix()}")
set(CADRUMO_RUST_ROOT "{root.as_posix()}")
set(CADRUMO_PIN_rust_target "{selected_target or triple}")
set(build_toolchain "{{}}")
add_subdirectory(native)
include("{REPO_ROOT.as_posix()}/native/cmake/ToolchainIdentity.cmake")
include("{REPO_ROOT.as_posix()}/native/cmake/DesktopRust.cmake")
cadrumo_desktop_rust_environment(selected)
file(WRITE "${{CMAKE_BINARY_DIR}}/build-toolchain.json" "${{build_toolchain}}")
add_custom_target(probe COMMAND "${{CMAKE_COMMAND}}" -E env --unset=CARGO_BUILD_TARGET
  ${{selected}} "{Path(node).as_posix()}" "{probe.as_posix()}" "{result.as_posix()}" VERBATIM)
''',
        encoding="utf-8",
    )
    return source, tmp_path / "build", result


def _configure(source: Path, build: Path) -> subprocess.CompletedProcess[str]:
    cmake = shutil.which("cmake")
    assert cmake is not None
    return subprocess.run(  # noqa: S603 -- trusted generated CMake fixture
        [cmake, "-S", str(source), "-B", str(build)], capture_output=True, text=True, check=False
    )


def test_generated_desktop_environment_executes_admitted_cargo_and_preserves_locator(tmp_path: Path) -> None:
    source, build, result = _fixture(tmp_path)
    configured = _configure(source, build)
    assert configured.returncode == 0, configured.stdout + configured.stderr
    descriptor: dict[str, Any] = json.loads((build / "build-toolchain.json").read_text(encoding="utf-8"))
    assert len(builder_inputs(descriptor)) == 3
    poison = tmp_path / "poison"
    poison.mkdir()
    rust_root, _, suffix = _rust()
    (poison / ("cargo" + suffix)).write_bytes(b"unusable ambient Cargo")
    cmake = shutil.which("cmake")
    assert cmake is not None
    completed = subprocess.run(  # noqa: S603 -- trusted generated CMake fixture and admitted native Rust tools
        [cmake, "--build", str(build), "--config", "Release", "--target", "probe"],
        env={
            **os.environ,
            "PATH": str(poison) + os.pathsep + os.environ["PATH"],
            "CARGO_BUILD_TARGET": "poison-target",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    observed = json.loads(result.read_text(encoding="utf-8"))
    assert observed["cargo"].startswith("cargo " + rust_root.name.split("-", 1)[0] + " ")
    assert observed["rustc"] == descriptor["builder_files"]["rust/rustc"]["path"]
    assert observed["rustdoc"] == descriptor["builder_files"]["rust/rustdoc"]["path"]
    assert observed["lib"] == "first;second"
    assert observed["target"] is None


def test_desktop_refuses_foreign_rust_host_before_producing_wrong_locator(tmp_path: Path) -> None:
    source, build, _ = _fixture(tmp_path, selected_target="foreign-unknown-target")
    configured = _configure(source, build)
    assert configured.returncode != 0
    assert "Desktop native host must match" in configured.stderr
