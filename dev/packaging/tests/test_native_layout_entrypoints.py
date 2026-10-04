"""Native console entrypoints must name declared console scripts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.packaging.native.layout import entrypoint_files, load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _checkout(root: Path, entrypoints: dict[str, str], scripts: dict[str, str]) -> Path:
    (root / "native/platforms").mkdir(parents=True)
    shared = {
        "abi": 1,
        "paths": {"native": "bin"},
        "files": {},
        "entrypoints": entrypoints,
        "platforms": {"windows-x64": "platforms/windows-x64.json"},
    }
    platform = {
        "platform": "windows-x64",
        "paths": {"executable": "python.exe"},
        "files": {},
        "entrypoint_suffix": ".exe",
    }
    (root / "native/package-layout.json").write_text(json.dumps(shared), encoding="utf-8")
    (root / "native/platforms/windows-x64.json").write_text(json.dumps(platform), encoding="utf-8")
    lines = "\n".join(f"{json.dumps(name)} = {json.dumps(target)}" for name, target in scripts.items())
    (root / "pyproject.toml").write_text(f'[project]\nname = "x"\n\n[project.scripts]\n{lines}\n', encoding="utf-8")
    return root


def test_declared_console_script_maps_to_a_package_root_executable(tmp_path: Path) -> None:
    root = _checkout(tmp_path, {"cadrumo-runtime": "Runtime"}, {"cadrumo-runtime": "pkg.runtime:main"})

    layout = load_layout("windows-x64", root=root)

    assert entrypoint_files(layout) == {"cadrumo-runtime": "cadrumo-runtime.exe"}


def test_undeclared_console_script_is_refused(tmp_path: Path) -> None:
    root = _checkout(tmp_path, {"cadrumo-runtime": "Runtime"}, {"aeat": "pkg.cli:main"})

    with pytest.raises(ValueError, match="not a declared console script: cadrumo-runtime"):
        load_layout("windows-x64", root=root)


@pytest.mark.parametrize("name", ["cadrumo')", "Cadrumo-runtime", "cadrumo--runtime", "-runtime", "cadrumo runtime"])
def test_entrypoint_names_that_cannot_be_embedded_safely_are_refused(tmp_path: Path, name: str) -> None:
    root = _checkout(tmp_path, {name: "Runtime"}, {name: "pkg.runtime:main"})

    with pytest.raises(ValueError, match="not a declared console script"):
        load_layout("windows-x64", root=root)


def test_checkout_layout_declares_the_runtime_entrypoint() -> None:
    layout = load_layout("windows-x64")

    assert entrypoint_files(layout)["cadrumo-runtime"] == "cadrumo-runtime.exe"
