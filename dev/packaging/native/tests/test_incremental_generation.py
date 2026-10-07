"""Generated contracts and action identities isolate changes by their actual consumers."""

from __future__ import annotations

import argparse
import copy
import io
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ...runtime_wheelhouse_contract import LockedWheel
from .. import cmake_build, provision
from ..cmake_build import action_toolchain
from ..generate import generate
from ..metadata import generate as generate_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _freeze_outputs(root: Path) -> dict[str, tuple[bytes, int]]:
    for path in root.iterdir():
        if path.is_file():
            os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    return _outputs(root)


def _outputs(root: Path) -> dict[str, tuple[bytes, int]]:
    return {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in root.iterdir() if path.is_file()}


def test_contract_rerun_preserves_outputs_and_restores_deleted_projection(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path, target="windows-x86-64")
    baseline = _freeze_outputs(tmp_path)
    generate(REPO_ROOT, tmp_path, target="windows-x86-64")
    assert _outputs(tmp_path) == baseline
    (tmp_path / "contract.rs").unlink()
    generate(REPO_ROOT, tmp_path, target="windows-x86-64")
    assert (tmp_path / "contract.rs").read_bytes() == baseline["contract.rs"][0]
    assert _outputs(tmp_path)["contract.h"] == baseline["contract.h"]
    generate(REPO_ROOT, tmp_path, channel="preview", target="windows-x86-64")
    assert _outputs(tmp_path)["contract.h"] == baseline["contract.h"]
    assert (tmp_path / "contract.rs").read_bytes() != baseline["contract.rs"][0]


def test_metadata_change_preserves_unaffected_icon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    png = io.BytesIO()
    Image.new("RGBA", (256, 256), "blue").save(png, format="PNG")
    monkeypatch.setitem(sys.modules, "resvg_py", SimpleNamespace(svg_to_bytes=lambda **kwargs: png.getvalue()))
    generate_metadata(tmp_path, 1, "2026-10-07", tmp_path, target="windows-x86-64")
    baseline = _freeze_outputs(tmp_path)
    generate_metadata(tmp_path, 1, "2026-10-07", tmp_path, target="windows-x86-64")
    assert _outputs(tmp_path) == baseline
    generate_metadata(tmp_path, 2, "2026-10-07", tmp_path, target="windows-x86-64")
    after = _outputs(tmp_path)
    assert after["cadrumo.ico"] == baseline["cadrumo.ico"]
    assert after["interpreter.rc"][0] != baseline["interpreter.rc"][0]
    assert after["build_metadata.h"][0] != baseline["build_metadata.h"][0]


@pytest.mark.parametrize("action", ["tools", "provision", "product"])
def test_desktop_changes_do_not_invalidate_native_actions(action: str) -> None:
    configured = {
        "builder_files": {
            "CADRUMO_UV": {"path": "uv", "sha256": "uv-one"},
            "CMAKE_C_COMPILER": {"path": "cc", "sha256": "cc-one"},
            "desktop/npm-lock": {"path": "lock", "sha256": "desktop-one"},
        }
    }
    baseline = action_toolchain(configured, action, "windows-x86-64")
    changed = copy.deepcopy(configured)
    changed["builder_files"]["desktop/npm-lock"]["sha256"] = "desktop-two"
    assert action_toolchain(changed, action, "windows-x86-64") == baseline
    changed["builder_files"]["CMAKE_C_COMPILER"]["sha256"] = "cc-two"
    assert action_toolchain(changed, action, "windows-x86-64") == baseline
    changed["builder_files"]["CADRUMO_UV"]["sha256"] = "uv-two"
    assert action_toolchain(changed, action, "windows-x86-64") != baseline


def test_cargo_crate_types_and_consumer_preserve_sibling_artifacts(tmp_path: Path) -> None:
    cargo = shutil.which("cargo")
    assert cargo is not None
    (tmp_path / "src").mkdir()
    manifest = tmp_path / "Cargo.toml"
    manifest.write_text(
        '[package]\nname="incremental-fixture"\nversion="0.0.0"\nedition="2024"\n[lib]\ncrate-type=["rlib"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src/lib.rs").write_text(
        '#[unsafe(no_mangle)] pub extern "C" fn answer() -> u32 { 42 }\n', encoding="utf-8"
    )
    consumer = tmp_path / "src/main.rs"
    consumer.write_text('fn main() { println!("original"); }\n', encoding="utf-8")
    output = tmp_path / "target/debug"

    def build(*arguments: str) -> None:
        result = run_command(
            [cargo, *arguments, "--offline", "--manifest-path", str(manifest), "--target-dir", str(output.parent)],
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    build("rustc", "--lib", "--crate-type", "staticlib")
    static = output / ("incremental_fixture.lib" if os.name == "nt" else "libincremental_fixture.a")
    before_static = (static.read_bytes(), static.stat().st_mtime_ns)
    build("rustc", "--lib", "--crate-type", "cdylib")
    shared = output / (
        "incremental_fixture.dll"
        if os.name == "nt"
        else "libincremental_fixture.dylib"
        if sys.platform == "darwin"
        else "libincremental_fixture.so"
    )
    before_shared = (shared.read_bytes(), shared.stat().st_mtime_ns)
    build("build", "--bin", "incremental-fixture")
    build("rustc", "--lib", "--crate-type", "staticlib")
    build("rustc", "--lib", "--crate-type", "cdylib")
    assert (static.read_bytes(), static.stat().st_mtime_ns) == before_static
    assert (shared.read_bytes(), shared.stat().st_mtime_ns) == before_shared

    consumer.write_text('fn main() { println!("changed"); }\n', encoding="utf-8")
    build("build", "--bin", "incremental-fixture")
    assert (static.read_bytes(), static.stat().st_mtime_ns) == before_static
    assert (shared.read_bytes(), shared.stat().st_mtime_ns) == before_shared


def test_changed_wheel_closure_reuses_sdk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A runtime dependency update neither calls SDK acquisition nor touches SDK bytes."""
    wheel = LockedWheel("fixture", "1", "fixture-1-py3-none-any.whl", "https://example.test/one", "a" * 64, 1)
    monkeypatch.setattr(cmake_build, "plan_target_wheels", lambda *args: (wheel,))
    sdk_identity = action_toolchain({}, "sdk", "windows-x86-64")
    dependency_identity = action_toolchain({}, "provision", "windows-x86-64")
    wheel = LockedWheel("fixture", "2", "fixture-2-py3-none-any.whl", "https://example.test/two", "b" * 64, 1)
    assert action_toolchain({}, "sdk", "windows-x86-64") == sdk_identity
    assert action_toolchain({}, "provision", "windows-x86-64") != dependency_identity

    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "build-toolchain.json").write_text("{}", encoding="utf-8")
    paths = {name: tmp_path / name for name in ("runtime", "generated", "python_sdk")}
    monkeypatch.setattr(cmake_build, "build_paths", lambda build: paths)
    sdk = paths["python_sdk"] / "sdk"
    sdk.mkdir(parents=True)
    (sdk / "python.h").write_text("stable SDK bytes", encoding="utf-8")
    baseline = _freeze_outputs(sdk)
    monkeypatch.setattr(cmake_build, "load_layout", lambda target: {"sdk": {"root": "sdk"}})
    monkeypatch.setattr(provision, "load_layout", lambda target: {"sdk": {"root": "sdk"}})
    monkeypatch.setattr(provision, "selected_uv", lambda *args, **kwargs: "configured-uv")
    monkeypatch.setattr(provision, "plan_target_wheels", lambda *args: (wheel,))

    def unexpected_sdk(*args: object) -> None:
        raise AssertionError("A dependency closure build must not reacquire the SDK")

    monkeypatch.setattr(provision, "backend", unexpected_sdk)

    def install(command: list[str], **kwargs: object) -> SimpleNamespace:
        dependencies = Path(command[command.index("--target") + 1])
        dependencies.mkdir()
        (dependencies / "fixture.py").write_text(wheel.version, encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(provision, "run_command", install)
    for version in ("2", "3"):
        wheel = LockedWheel(
            "fixture", version, f"fixture-{version}-py3-none-any.whl", "https://example.test/w", "c" * 64, 1
        )
        cmake_build.build_action(tmp_path, argparse.Namespace(action="provision", target="windows-x86-64"))
        assert (paths["runtime"] / "dependencies/fixture.py").read_text(encoding="utf-8") == version
        assert _outputs(sdk) == baseline
