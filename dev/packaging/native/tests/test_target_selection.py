"""Target markers and wheel floors remain independent of the running host."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...runtime_wheel_selection import marker_environment, plan_target_wheels
from ...runtime_wheelhouse_contract import target_platform
from ..layout import distribution_target, load_layout
from ..target import toolchain_for_target, uv_environment, uv_platform

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_windows_alias_resolves_the_canonical_distribution() -> None:
    assert load_layout("windows-x86-64") == load_layout("windows-x64")
    assert distribution_target(load_layout("windows-x86-64")) == "windows-x86-64"


def test_foreign_markers_use_exact_python_and_target_architecture() -> None:
    environment = marker_environment(target_platform("linux-aarch64"), "3.13.11")
    assert environment["sys_platform"] == "linux"
    assert environment["platform_machine"] == "aarch64"
    assert environment["python_full_version"] == "3.13.11"
    assert environment["implementation_version"] == "3.13.11"
    assert environment["platform_release"] == ""
    assert environment["platform_version"] == ""


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("windows-x86-64", "x86_64-pc-windows-msvc"),
        ("linux-x86-64", "x86_64-manylinux_2_28"),
        ("linux-aarch64", "aarch64-manylinux_2_28"),
        ("macos-arm64", "aarch64-apple-darwin"),
    ],
)
def test_tool_spelling_retains_the_declared_architecture_and_floor(target: str, expected: str) -> None:
    assert uv_platform(target) == expected


def test_foreign_target_selects_linux_wheels_and_excludes_windows_packages() -> None:
    wheels = plan_target_wheels(REPO_ROOT, "linux-aarch64", "3.13.11")
    assert wheels
    assert "pywin32" not in {wheel.distribution for wheel in wheels}
    assert all(wheel.filename.endswith(("any.whl", "aarch64.whl")) for wheel in wheels)
    assert any("manylinux" in wheel.filename for wheel in wheels)


def test_unknown_target_cannot_fall_back_to_host() -> None:
    with pytest.raises(ValueError, match="Unsupported distribution target"):
        plan_target_wheels(REPO_ROOT, "linux-armv7", "3.13.11")


def test_macos_installer_floor_ignores_the_host_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MACOSX_DEPLOYMENT_TARGET", "99.0")
    assert uv_environment("macos-arm64")["MACOSX_DEPLOYMENT_TARGET"] == "14.0"
    assert os.environ["MACOSX_DEPLOYMENT_TARGET"] == "99.0"


def test_sdk_pins_never_fall_back_to_another_target(tmp_path: Path) -> None:
    assert toolchain_for_target("windows-x86-64")["cpython_source"].startswith("https://api.nuget.org/")
    tools = json.loads((REPO_ROOT / "native/toolchain.json").read_text(encoding="utf-8"))
    for name in ("linux-x86-64", "linux-aarch64", "macos-arm64"):
        tools["targets"][name].pop("cpython_source", None)
        tools["targets"][name].pop("cpython_sha256", None)
    (tmp_path / "native").mkdir()
    (tmp_path / "native/toolchain.json").write_text(json.dumps(tools), encoding="utf-8")
    for name in ("linux-x86-64", "linux-aarch64", "macos-arm64"):
        with pytest.raises(ValueError, match="SDK source/trust pins are not enrolled"):
            toolchain_for_target(name, root=tmp_path)
