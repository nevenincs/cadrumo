"""The clean desktop producer binds executable bytes and its captured npm lock."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from ..build_toolchain import builder_inputs, native_toolchain_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_desktop_tools_admit_bytes_without_invalidating_native_cargo(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    tools = tmp_path / "host tools"
    tools.mkdir()
    node = tools / "node.exe"
    node.write_bytes(b"selected node version one")
    wrapper = tools / "npm.cmd"
    wrapper.write_bytes(b"selected npm wrapper")
    npm = tools / "node_modules/npm"
    (npm / "bin").mkdir(parents=True)
    cli = npm / "bin/npm-cli.js"
    cli.write_bytes(b"require('../lib/cli.js')")
    (npm / "package.json").write_text('{"name":"npm","version":"1.0.0"}', encoding="utf-8")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    lock = frontend / "package-lock.json"
    lock.write_text('{"lockfileVersion":3}', encoding="utf-8")
    output = tmp_path / "identity.json"
    script = tmp_path / "identity.cmake"
    script.write_text(
        f'''cmake_minimum_required(VERSION 4.4)
set(build_toolchain "{{}}")
include("{REPO_ROOT.as_posix()}/native/cmake/ToolchainIdentity.cmake")
set(CADRUMO_NODE "{node.as_posix()}")
set(CADRUMO_NPM "{wrapper.as_posix()}")
set(desktop_frontend "{frontend.as_posix()}")
include("{REPO_ROOT.as_posix()}/native/cmake/DesktopTools.cmake")
file(WRITE "{output.as_posix()}" "${{build_toolchain}}")
''',
        encoding="utf-8",
    )

    def configure() -> dict[str, Any]:
        subprocess.run([cmake, "-P", str(script)], check=True, capture_output=True, text=True)  # noqa: S603 -- trusted generated CMake fixture
        return json.loads(output.read_text(encoding="utf-8"))

    configured = configure()
    assert set(configured["builder_files"]) == {
        "desktop/node",
        "desktop/npm-wrapper",
        "desktop/npm-cli",
        "desktop/npm-package",
        "desktop/npm-lock",
    }
    assert configured["desktop_tools"]["npm_cli"] == cli.as_posix()
    assert len(builder_inputs(configured)) == 5
    native_key = native_toolchain_identity(configured)
    node.write_bytes(b"different bytes with the same reported version")
    with pytest.raises(ValueError, match="desktop/node"):
        builder_inputs(configured)
    refreshed = configure()
    assert len(builder_inputs(refreshed)) == 5
    assert native_toolchain_identity(refreshed) == native_key
    lock.write_text('{"lockfileVersion":3,"packages":{"changed":{}}}', encoding="utf-8")
    with pytest.raises(ValueError, match="desktop/npm-lock"):
        builder_inputs(refreshed)
