"""CMake-selected native rewriting tools are bound to absolute content identities."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..assemble import native_assembly_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_cmake_selected_tools_reject_content_drift_without_shipping_host_paths(tmp_path: Path) -> None:
    paths = {name: tmp_path / name for name in ("readelf", "patchelf")}
    for name, path in paths.items():
        path.write_bytes(f"reviewed {name}".encode())
    script = tmp_path / "configure.cmake"
    output = tmp_path / "toolchain.json"
    script.write_text(
        "cmake_minimum_required(VERSION 4.4)\nset(target_system Linux)\n"
        'set(CADRUMO_TARGET linux-aarch64)\nset(build_toolchain "{}")\n'
        + "".join(f'set(CADRUMO_{name.upper()} "{path.as_posix()}")\n' for name, path in paths.items())
        + f'include("{(REPO_ROOT / "native/cmake/AssemblyTools.cmake").as_posix()}")\n'
        + f'file(WRITE "{output.as_posix()}" "${{build_toolchain}}")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    completed = run_command([cmake, "-P", str(script)], cwd=tmp_path, timeout_seconds=30)
    assert completed.returncode == 0, completed.stderr
    provenance = json.loads(output.read_text(encoding="utf-8"))
    contract = {"backend": "linux", "platform": "linux-aarch64"}
    projected = native_assembly_layout(contract, {"build_toolchain": provenance})
    assert projected["native_tools"] == {name: path.as_posix() for name, path in paths.items()}
    assert "native_tools" not in contract
    paths["patchelf"].write_bytes(b"substituted binary")
    with pytest.raises(ValueError, match="differs from CMake provenance"):
        native_assembly_layout(contract, {"build_toolchain": provenance})


def test_native_assembly_refuses_ambient_tool_and_missing_signing_identity(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit absolute readelf"):
        native_assembly_layout({"backend": "linux"}, {"build_toolchain": {"native_tools": {"readelf": "readelf"}}})
    paths = {name: tmp_path / name for name in ("install_name_tool", "codesign")}
    for path in paths.values():
        path.write_bytes(b"reviewed tool")
    provenance = {
        "native_tools": {name: str(path) for name, path in paths.items()},
        "native_tool_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
    }
    with pytest.raises(ValueError, match="explicit signing identity"):
        native_assembly_layout({"backend": "macos"}, {"build_toolchain": provenance})
