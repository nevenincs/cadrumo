"""Direct generator commands cannot create outputs outside enrolled build targets."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from .cmake_build_fixture import enrolled_cmake_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("module", "arguments"),
    [
        ("identity", ["--target", "windows-x86-64", "--output", "{output}"]),
        ("generate", ["{output}", "--target", "windows-x86-64"]),
        ("metadata", ["{output}", "--number", "1", "--date", "2026-10-16", "--tools", "{root}"]),
        (
            "product",
            ["--output", "{output}", "--python", "{python}", "--dependencies", "{root}", "--target", "windows-x86-64"],
        ),
        ("provision", ["{output}", "--target", "windows-x86-64"]),
        ("build_toolchain", ["{root}", "{output}"]),
        ("linux_desktop_runtime", ["--payload", "{root}", "--output", "{output}"]),
        ("assemble", ["--destination", "{output}"]),
    ],
)
def test_generator_refuses_external_output_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str, arguments: list[str]
) -> None:
    enrolled_cmake_root(tmp_path, monkeypatch)
    output = tmp_path / "outside-build"
    arguments = [item.format(output=output, root=tmp_path, python=sys.executable) for item in arguments]
    result = run_command([sys.executable, "-B", "-m", f"dev.packaging.native.{module}", *arguments], cwd=REPO_ROOT)
    assert result.returncode != 0
    assert "require_enrolled_output" in result.stderr
    assert not output.exists()
