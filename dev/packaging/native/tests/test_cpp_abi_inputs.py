"""Configured C++ floor evidence must precede any delivered image execution."""

from __future__ import annotations

import copy
import json
import shutil
import struct
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from .. import artifact_verify, cpp_abi_inputs, linux_cxx_abi
from ..hashing import digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXPORTS = """Version definition section '.gnu.version_d' contains 3 entries:
  000000: Rev: 1 Flags: BASE Index: 1 Cnt: 1 Name: libstdc++.so.6
  000010: Rev: 1 Flags: none Index: 2 Cnt: 1 Name: GLIBCXX_3.4.25
  000020: Rev: 1 Flags: none Index: 3 Cnt: 1 Name: CXXABI_1.3.11
"""
_NEEDS = """Version needs section '.gnu.version_r' contains 1 entry:
  000000: Version: 1 File: libstdc++.so.6 Cnt: 2
  000010: Name: GLIBCXX_3.4.25 Flags: none Version: 2
  000020: Name: CXXABI_1.3.11 Flags: none Version: 3
"""


def _elf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 62)
    path.write_bytes(data)
    return path


def _record(path: Path) -> dict[str, str]:
    return {"path": str(path), "resolved": str(path.resolve()), "link_text": "", "sha256": digest(path)}


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "canonical inputs"
    (root / "native").mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / "native/toolchain.json", root / "native/toolchain.json")
    pins = json.loads((root / "native/toolchain.json").read_text(encoding="utf-8"))
    pin = pins["targets"]["linux-x86-64"]["cpp_abi_floor"]
    provider = _elf(tmp_path / "retained floor/lib/libstdc++.so.6.0.25")
    proof = provider.parent.parent / "provider.json"
    proof.write_text(
        json.dumps(
            {
                "schema": "cadrumo.linux-cxx-floor.v1",
                "target": "linux-x86-64",
                "floor": "glibc-2.28",
                "image": pin["image"],
                "provider": {
                    "path": provider.relative_to(proof.parent).as_posix(),
                    "sha256": digest(provider),
                    "source_path": "/usr/lib64/libstdc++.so.6.0.25",
                    "soname": "libstdc++.so.6",
                    "elf_machine": 62,
                },
            }
        ),
        encoding="utf-8",
    )
    tool = tmp_path / "selected builder/readelf"
    tool.parent.mkdir()
    tool.write_bytes(b"selected readelf implementation")
    selection = cpp_abi_inputs.linux_cpp_abi_inputs("linux-x86-64", proof, root=root)
    configured = {
        "linux_cpp_abi": selection,
        "builder_files": {
            "linux_cpp_abi/proof": _record(proof),
            "linux_cpp_abi/provider": _record(provider),
            "native/readelf": _record(tool),
        },
        "native_tools": {"readelf": str(tool)},
        "native_tool_sha256": {"readelf": digest(tool)},
    }
    package = tmp_path / "package"
    image = _elf(package / "bin/cadrumo-python")
    manifest = {
        "build": {"target": "linux-x86-64"},
        "layout": {"platform": "linux-x86-64", "native_system_libraries": ["libstdc++.so.6"]},
        "files": {"bin/cadrumo-python": digest(image)},
        "user_docs": {"directory": "docs", "bundled": False},
        "inputs": {"build_toolchain": copy.deepcopy(configured)},
    }
    return dict(
        root=root, package=package, manifest=manifest, configured=configured, proof=proof, provider=provider, tool=tool
    )


def test_configured_inputs_reach_actual_abi_parser(inputs: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def read(command: list[str], **kwargs: Any) -> Any:
        calls.append(command)
        assert command[0] == str(inputs["tool"])
        return SimpleNamespace(
            returncode=0, stdout=_EXPORTS if command[-1] == str(inputs["provider"]) else _NEEDS, stderr=""
        )

    monkeypatch.setattr(linux_cxx_abi, "run_command", read)
    result = cpp_abi_inputs.verify_linux_cpp_abi_inputs(
        inputs["package"], inputs["manifest"], inputs["configured"], root=inputs["root"]
    )
    assert result is not None and result["floor"] == "glibc-2.28"
    assert [Path(command[-1]) for command in calls] == [inputs["provider"], inputs["package"] / "bin/cadrumo-python"]


@pytest.mark.parametrize(
    "changed", ["proof", "provider", "tool", "missing_proof", "image", "target", "packaged_identity"]
)
def test_changed_or_missing_admission_refuses_before_readelf(
    inputs: dict[str, Any], monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    calls = []
    monkeypatch.setattr(linux_cxx_abi, "run_command", lambda *args, **kwargs: calls.append(args))
    if changed in {"proof", "provider", "tool"}:
        path = inputs[changed]
        path.write_bytes(path.read_bytes() + b"changed")
    elif changed == "missing_proof":
        del inputs["configured"]["linux_cpp_abi"]
    elif changed == "image":
        path = inputs["root"] / "native/toolchain.json"
        pins = json.loads(path.read_text(encoding="utf-8"))
        pins["targets"]["linux-x86-64"]["cpp_abi_floor"]["image"] = "reviewed/floor@sha256:" + "0" * 64
        path.write_text(json.dumps(pins), encoding="utf-8")
    elif changed == "target":
        inputs["configured"]["linux_cpp_abi"]["target"] = "linux-aarch64"
    else:
        inputs["manifest"]["inputs"]["build_toolchain"]["linux_cpp_abi"]["proof_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        cpp_abi_inputs.verify_linux_cpp_abi_inputs(
            inputs["package"], inputs["manifest"], inputs["configured"], root=inputs["root"]
        )
    assert calls == []


def test_windows_verification_needs_no_linux_inputs(tmp_path: Path) -> None:
    assert cpp_abi_inputs.verify_linux_cpp_abi_inputs(tmp_path, {"build": {"target": "windows-x86-64"}}, {}) is None


def test_artifact_admission_precedes_external_or_shipped_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = tmp_path / "build"
    generated = build / "generated"
    generated.mkdir(parents=True)
    (generated / "build-toolchain.json").write_text("{}", encoding="utf-8")
    archive = build / "input.zip"
    archive.write_bytes(b"fixture archive bytes")
    manifest = {"build": {"target": "linux-x86-64"}}
    manifest_bytes = json.dumps(manifest).encode()
    contract = {"backend": "linux", "files": {"package_manifest": "manifest.json"}}
    monkeypatch.setattr(
        artifact_verify, "build_paths", lambda root: {"verification": root / "verification", "generated": generated}
    )
    monkeypatch.setattr(artifact_verify, "load_layout", lambda target: contract)
    monkeypatch.setattr(artifact_verify, "verify_release", lambda *args: None)

    def extract(path: Path, destination: Path) -> None:
        package = destination / "app"
        package.mkdir()
        (package / "manifest.json").write_bytes(manifest_bytes)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Missing Linux proof reached external/shipped image execution")

    monkeypatch.setattr(artifact_verify, "extract_bundle", extract)
    monkeypatch.setattr(artifact_verify, "backend", forbidden)
    monkeypatch.setattr(artifact_verify, "run_command", forbidden)
    locator = {
        "archive": str(archive),
        "archive_sha256": digest(archive),
        "manifest_sha256": digest_bytes(manifest_bytes),
        "target": "linux-x86-64",
        "release": {},
    }
    (build / "artifacts-Release.json").write_text(json.dumps(locator), encoding="utf-8")
    with pytest.raises(ValueError, match="CADRUMO_LINUX_CPP_ABI_PROOF"):
        artifact_verify.check(build, "Release")


def digest_bytes(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()


def test_cmake_projects_both_provider_inputs(inputs: dict[str, Any], tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake, "CMake is required by the common build regression"
    project = inputs["root"]
    script = f'''cmake_minimum_required(VERSION 3.25)
project(floor_inputs NONE)
set(target_system Linux)
set(CADRUMO_TARGET linux-x86-64)
set(CADRUMO_DEV_PYTHON "{Path(sys.executable).as_posix()}")
set(CADRUMO_READELF "{inputs["tool"].as_posix()}")
set(CADRUMO_PATCHELF "{inputs["tool"].as_posix()}")
set(CADRUMO_LINUX_CPP_ABI_PROOF "{inputs["proof"].as_posix()}")
set(build_toolchain "{{}}")
include("{(REPO_ROOT / "native/cmake/ToolchainIdentity.cmake").as_posix()}")
file(WRITE "${{CMAKE_BINARY_DIR}}/configured.json" "${{build_toolchain}}")
'''
    (project / "CMakeLists.txt").write_text(script, encoding="utf-8")
    binary = tmp_path / "configured build"
    result = run_command([cmake, "-S", str(project), "-B", str(binary)], cwd=project, timeout_seconds=60)
    assert result.returncode == 0, result.stdout + result.stderr
    configured = json.loads((binary / "configured.json").read_text(encoding="utf-8"))
    assert configured["linux_cpp_abi"] == inputs["configured"]["linux_cpp_abi"]
    for label in ("linux_cpp_abi/proof", "linux_cpp_abi/provider", "native/readelf"):
        actual, expected = configured["builder_files"][label], inputs["configured"]["builder_files"][label]
        assert Path(actual["path"]) == Path(expected["path"])
        assert Path(actual["resolved"]) == Path(expected["resolved"])
        assert actual["sha256"] == expected["sha256"] and actual["link_text"] == expected["link_text"]
    inputs["provider"].write_bytes(inputs["provider"].read_bytes() + b"changed")
    retry = run_command([cmake, "--build", str(binary)], cwd=project, timeout_seconds=60)
    assert retry.returncode != 0 and "floor provider bytes differ" in retry.stdout + retry.stderr
