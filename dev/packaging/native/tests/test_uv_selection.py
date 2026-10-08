"""Configured production actions cannot select a different uv through PATH."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from .. import cmake_build, product, provision
from ..build_toolchain import selected_uv

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _selection(path: Path) -> dict[str, Any]:
    return {
        "CADRUMO_UV": str(path),
        "builder_files": {
            "CADRUMO_UV": {
                "path": str(path),
                "resolved": str(path.resolve()),
                "link_text": "",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        },
    }


@pytest.mark.parametrize("action", ["provision", "product", "tools"])
def test_configured_actions_use_selected_uv_despite_path_reordering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    selected = tmp_path / "configured/uv.exe"
    ambient = tmp_path / "ambient/uv.exe"
    for path in (selected, ambient):
        path.parent.mkdir()
        path.write_bytes(path.parent.name.encode())
    configured = _selection(selected)
    monkeypatch.setenv("PATH", str(ambient.parent) + os.pathsep + os.environ.get("PATH", ""))

    class ObservedUvError(RuntimeError):
        pass

    def observe(command: list[str], **kwargs: object) -> Any:
        if command[1:2] == ["-I"]:
            pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
            return SimpleNamespace(returncode=0, stdout=pin + "\n", stderr="")
        assert command[0] == str(selected)
        raise ObservedUvError

    with pytest.raises(ObservedUvError):
        if action == "provision":
            monkeypatch.setattr(provision, "run_command", observe)
            monkeypatch.setattr(provision, "plan_target_wheels", lambda *args: ())
            monkeypatch.setattr(
                provision,
                "backend",
                lambda layout: SimpleNamespace(
                    provision_sdk=lambda destination, *args: destination / layout["sdk"]["root"]
                ),
            )
            provision.provision(tmp_path / "runtime", "windows-x86-64", build_toolchain=configured)
        elif action == "product":

            def snapshot(root: Path, files: object, destination: Path) -> None:
                destination.mkdir(parents=True)
                shutil.copyfile(root / "pyproject.toml", destination / "pyproject.toml")

            monkeypatch.setattr(product, "run_command", observe)
            monkeypatch.setattr(product, "repository_files", lambda root: ())
            monkeypatch.setattr(product, "snapshot", snapshot)
            monkeypatch.setattr(product, "stage_published_authority", lambda *args: None)
            dependencies = tmp_path / "dependencies"
            dependencies.mkdir()
            product.build_product(
                tmp_path / "product", Path(sys.executable), dependencies, "windows-x86-64", build_toolchain=configured
            )
        else:
            monkeypatch.setattr(cmake_build, "run_command", observe)
            build = tmp_path / "build"
            (build / "generated").mkdir(parents=True)
            (build / "build-paths.json").write_text(
                json.dumps(
                    {
                        "paths": {
                            "runtime": "runtime",
                            "generated": "generated",
                            "tools": "tools",
                        }
                    }
                ),
                encoding="utf-8",
            )
            (build / "generated/build-toolchain.json").write_text(json.dumps(configured), encoding="utf-8")
            cmake_build.build_action(build, argparse.Namespace(action="tools", target="windows-x86-64"))


def test_uv_byte_change_requires_reconfiguration_even_when_version_text_is_unchanged(tmp_path: Path) -> None:
    uv = tmp_path / "uv"
    uv.write_bytes(b"same version; original executable")
    project = tmp_path / "project"
    project.mkdir()
    output = project / "toolchain.json"
    (project / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(UvSelection LANGUAGES NONE)\n"
        'set(build_toolchain "{}")\n'
        f'set(CADRUMO_UV "{uv.as_posix()}")\n'
        'string(JSON build_toolchain SET "${build_toolchain}" CADRUMO_UV "\\"${CADRUMO_UV}\\"")\n'
        f'include("{(REPO_ROOT / "native/cmake/ToolchainIdentity.cmake").as_posix()}")\n'
        f'file(WRITE "{output.as_posix()}" "${{build_toolchain}}")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    command = [cmake, "-S", str(project), "-B", str(tmp_path / "build")]
    result = run_command(command, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    configured = json.loads(output.read_text(encoding="utf-8"))
    assert selected_uv(configured) == uv.as_posix()
    uv.write_bytes(b"same version; substituted executable")
    with pytest.raises(ValueError, match="CADRUMO_UV; reconfigure"):
        selected_uv(configured)
    result = run_command(command, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    refreshed = json.loads(output.read_text(encoding="utf-8"))
    assert selected_uv(refreshed) == uv.as_posix()
    assert refreshed["builder_files"]["CADRUMO_UV"]["sha256"] != configured["builder_files"]["CADRUMO_UV"]["sha256"]
