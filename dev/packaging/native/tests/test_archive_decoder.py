"""SDK decoding uses a selected builder identity and canonical source provenance."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..provision import provisioning_tools
from ..target import toolchain_for_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_cmake_decoder_projection_is_builder_only_and_refuses_drift(tmp_path: Path) -> None:
    decoder = tmp_path / "zstd"
    decoder.write_bytes(b"selected builder decoder")
    output = tmp_path / "build-toolchain.json"
    script = tmp_path / "configure.cmake"
    script.write_text(
        "cmake_minimum_required(VERSION 4.4)\n"
        'set(CADRUMO_TARGET linux-aarch64)\nset(build_toolchain "{}")\n'
        'string(JSON build_toolchain SET "${build_toolchain}" CADRUMO_TARGET "\\"${CADRUMO_TARGET}\\"")\n'
        f'file(READ "{(REPO_ROOT / "native/toolchain.json").as_posix()}" toolchain)\n'
        f'set(CADRUMO_ZSTD "{decoder.as_posix()}")\n'
        f'include("{(REPO_ROOT / "native/cmake/ArchiveTools.cmake").as_posix()}")\n'
        f'file(WRITE "{output.as_posix()}" "${{build_toolchain}}")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, "-P", str(script)], cwd=tmp_path, timeout_seconds=None)
    assert result.returncode == 0, result.stderr
    selected = json.loads(output.read_text(encoding="utf-8"))
    pins = toolchain_for_target("linux-aarch64")
    projected = provisioning_tools("linux-aarch64", selected)
    assert projected["cpython_archive_decoder"]["sha256"] == hashlib.sha256(decoder.read_bytes()).hexdigest()
    assert projected["cpython_archive_decoder"]["provenance"] == pins["cpython_archive_decoder_provenance"]
    assert "cpython_archive_decoder" not in pins
    assert projected["rust_target"] == pins["rust_target"]
    decoder.write_bytes(b"substituted decoder")
    with pytest.raises(ValueError, match="configured content identity"):
        provisioning_tools("linux-aarch64", selected)


@pytest.mark.parametrize("defect", ["missing", "target", "provenance", "relative"])
def test_decoder_refuses_unselected_host_or_source(tmp_path: Path, defect: str) -> None:
    decoder = tmp_path / "zstd"
    decoder.write_bytes(b"selected")
    configured = {
        "CADRUMO_TARGET": "linux-x86-64",
        "cpython_archive_decoder": {
            "executable": str(decoder),
            "sha256": hashlib.sha256(decoder.read_bytes()).hexdigest(),
            "provenance": dict(toolchain_for_target("linux-x86-64")["cpython_archive_decoder_provenance"]),
        },
    }
    if defect == "target":
        configured["CADRUMO_TARGET"] = "macos-arm64"
    elif defect == "provenance":
        configured["cpython_archive_decoder"]["provenance"]["release"] = "unreviewed"
    elif defect == "relative":
        configured["cpython_archive_decoder"]["executable"] = "zstd"
    with pytest.raises(ValueError, match=r"explicit build toolchain|provenance|absolute builder"):
        provisioning_tools("linux-x86-64", None if defect == "missing" else configured)


def test_windows_sdk_needs_no_posix_archive_decoder() -> None:
    assert provisioning_tools("windows-x86-64", None) == toolchain_for_target("windows-x86-64")
