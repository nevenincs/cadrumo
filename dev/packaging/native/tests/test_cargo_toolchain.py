"""Native toolchain changes rebuild actual Cargo outputs without touching desktop outputs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ...command_execution import run_command
from .. import cmake_build
from ..cmake_build import run_configured_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _toolchain(wrapper: Path) -> dict[str, Any]:
    return {
        "builder_files": {
            "CADRUMO_RUST_LINKER": {
                "path": str(wrapper),
                "resolved": str(wrapper.resolve()),
                "link_text": "",
                "sha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(),
            }
        }
    }


def test_toolchain_change_rebuilds_real_crate_and_preserves_desktop_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cargo = shutil.which("cargo")
    assert cargo is not None
    build = tmp_path / "build"
    (build / "generated").mkdir(parents=True)
    native = build / "cargo/native"
    desktop = build / "cargo/desktop"
    desktop.mkdir(parents=True)
    sentinel = desktop / "retain"
    sentinel.write_bytes(b"desktop bytes")
    (build / "build-paths.json").write_text(
        json.dumps(
            {
                "paths": {
                    "generated": "generated",
                    "cargo": "cargo/native",
                    "desktop_cargo": "cargo/desktop",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CARGO_TARGET_DIR", str(native))
    counter = tmp_path / "compilations"
    monkeypatch.setenv("CADRUMO_FIXTURE_COMPILATIONS", str(counter))
    crate = tmp_path / "crate"
    (crate / "src").mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname="toolchain-fixture"\nversion="0.0.0"\nedition="2024"\n', encoding="utf-8"
    )
    (crate / "src/main.rs").write_text('fn main() { println!("real native build"); }\n', encoding="utf-8")
    (crate / "build.rs").write_text(
        'fn main() { let p=std::env::var("CADRUMO_FIXTURE_COMPILATIONS").unwrap(); '
        'let n=std::fs::read_to_string(&p).unwrap_or("0".into()).parse::<u32>().unwrap(); '
        'std::fs::write(p, (n+1).to_string()).unwrap(); println!("cargo::rerun-if-changed=build.rs"); }\n',
        encoding="utf-8",
    )
    wrapper = tmp_path / "linker-wrapper"
    wrapper.write_bytes(b"reviewed wrapper bytes")
    configured = _toolchain(wrapper)
    command = [cargo, "build", "--offline", "--manifest-path", str(crate / "Cargo.toml")]
    for expected in (1, 1):
        result = run_configured_command(build, configured, command)
        assert result.returncode == 0, result.stdout + result.stderr
        assert counter.read_text(encoding="utf-8") == str(expected)
    wrapper.write_bytes(b"changed reviewed wrapper bytes")
    with pytest.raises(ValueError, match="CADRUMO_RUST_LINKER; reconfigure"):
        run_configured_command(build, configured, command)
    result = run_configured_command(build, _toolchain(wrapper), command)
    assert result.returncode == 0, result.stdout + result.stderr
    assert counter.read_text(encoding="utf-8") == "2"
    assert sentinel.read_bytes() == b"desktop bytes"
    with pytest.raises(ValueError, match="override escapes"):
        run_configured_command(build, _toolchain(wrapper), [*command, "--target-dir", str(desktop)])
    assert sentinel.read_bytes() == b"desktop bytes"


def test_overlapping_previous_native_cargo_root_is_refused_before_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cargo = shutil.which("cargo")
    assert cargo is not None
    (tmp_path / "build-paths.json").write_text(
        json.dumps(
            {
                "paths": {
                    "generated": "generated",
                    "cargo": "cargo",
                    "desktop_cargo": "cargo/desktop",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CARGO_TARGET_DIR", str(tmp_path / "cargo"))
    with pytest.raises(ValueError, match="isolated from desktop"):
        run_configured_command(tmp_path, {}, [cargo, "build"])


@pytest.mark.parametrize("failed_action", ["clean", "build"])
def test_failed_cargo_action_keeps_identity_unpublished_and_retry_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_action: str
) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    native = tmp_path / "cargo/native"
    (tmp_path / "build-paths.json").write_text(
        json.dumps(
            {
                "paths": {
                    "generated": "generated",
                    "cargo": "cargo/native",
                    "desktop_cargo": "cargo/desktop",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CARGO_TARGET_DIR", str(native))
    inherited_path = os.pathsep.join((str(tmp_path / "path with spaces"), os.environ["PATH"]))
    monkeypatch.setenv("PATH", inherited_path)
    calls = []
    failed = False

    def command(argv: list[str], **kwargs: object) -> Any:
        nonlocal failed
        assert kwargs["environment"] == dict(os.environ, PATH=os.pathsep.join((str(tmp_path), inherited_path)))
        calls.append(argv[1])
        status = 0
        if argv[1] == failed_action and not failed:
            status, failed = 1, True
        return SimpleNamespace(returncode=status, stdout="", stderr="")

    monkeypatch.setattr(cmake_build, "run_command", command)
    argv = [str(tmp_path / "cargo.exe"), "build"]
    assert run_configured_command(tmp_path, {}, argv).returncode == 1
    assert not list(generated.glob("rust-toolchain-*.txt"))
    assert run_configured_command(tmp_path, {}, argv).returncode == 0
    assert calls == (["clean", "clean", "build"] if failed_action == "clean" else ["clean", "build", "clean", "build"])
    assert len(list(generated.glob("rust-toolchain-*.txt"))) == 1
    assert os.environ["PATH"] == inherited_path


def test_configured_clippy_ignores_conflicting_ambient_subcommands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rustc = shutil.which("rustc")
    assert rustc is not None
    sysroot = run_command([rustc, "--print", "sysroot"], cwd=tmp_path)
    assert sysroot.returncode == 0, sysroot.stderr
    selected_bin = Path(sysroot.stdout.strip()) / "bin"
    suffix = ".exe" if os.name == "nt" else ""
    cargo = selected_bin / f"cargo{suffix}"
    assert cargo.is_file()
    assert (selected_bin / f"cargo-clippy{suffix}").is_file()
    assert (selected_bin / f"clippy-driver{suffix}").is_file()

    poison = tmp_path / "conflicting tools"
    poison.mkdir()
    source = poison / "main.rs"
    source.write_text('fn main() { eprintln!("ambient clippy selected"); std::process::exit(97); }\n', encoding="utf-8")
    executable = poison / f"cargo-clippy{suffix}"
    compiled = run_command([str(selected_bin / f"rustc{suffix}"), str(source), "-o", str(executable)], cwd=tmp_path)
    assert compiled.returncode == 0, compiled.stderr
    shutil.copyfile(executable, poison / f"clippy-driver{suffix}")
    (poison / f"clippy-driver{suffix}").chmod(executable.stat().st_mode)

    native = tmp_path / "cargo/native"
    (tmp_path / "build-paths.json").write_text(
        json.dumps({"paths": {"generated": "generated", "cargo": "cargo/native", "desktop_cargo": "cargo/desktop"}}),
        encoding="utf-8",
    )
    crate = tmp_path / "crate"
    (crate / "src").mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname="clippy-path-fixture"\nversion="0.0.0"\nedition="2024"\n', encoding="utf-8"
    )
    (crate / "src/main.rs").write_text('fn main() { println!("selected clippy"); }\n', encoding="utf-8")
    monkeypatch.setenv("CARGO_HOME", str(tmp_path / "cargo-home"))
    monkeypatch.setenv("CARGO_TARGET_DIR", str(native))
    monkeypatch.setenv("RUSTC", str(selected_bin / f"rustc{suffix}"))
    monkeypatch.setenv("RUSTDOC", str(selected_bin / f"rustdoc{suffix}"))
    inherited_path = os.pathsep.join((str(poison), str(tmp_path / "retained path"), os.environ["PATH"]))
    monkeypatch.setenv("PATH", inherited_path)
    command = [str(cargo), "clippy", "--offline", "--manifest-path", str(crate / "Cargo.toml"), "--", "-D", "warnings"]
    baseline = run_command(command, cwd=tmp_path)
    assert baseline.returncode == 97, baseline.stdout + baseline.stderr
    assert "ambient clippy selected" in baseline.stderr
    result = run_configured_command(tmp_path, {}, command)
    assert result.returncode == 0, result.stdout + result.stderr
    assert os.environ["PATH"] == inherited_path


def test_linked_native_root_is_refused_before_clean_without_sibling_damage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    native = tmp_path / "build/cargo/native"
    desktop = native.parent / "desktop"
    desktop.mkdir(parents=True)
    sentinel = desktop / "retain"
    sentinel.write_bytes(b"retain desktop")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "retain"
    outside_file.write_bytes(b"retain outside")
    try:
        native.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("The runner cannot create a native target directory symlink")
    build = native.parents[1]
    (build / "build-paths.json").write_text(
        json.dumps(
            {
                "paths": {
                    "generated": "generated",
                    "cargo": "cargo/native",
                    "desktop_cargo": "cargo/desktop",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CARGO_TARGET_DIR", str(native))

    def unexpected_command(*args: object, **kwargs: object) -> Any:
        raise AssertionError("Linked target root must be refused before any Cargo command")

    monkeypatch.setattr(cmake_build, "run_command", unexpected_command)
    with pytest.raises(ValueError, match="Linked CMake output directory"):
        run_configured_command(build, {}, [str(tmp_path / "cargo.exe"), "build"])
    assert sentinel.read_bytes() == b"retain desktop"
    assert outside_file.read_bytes() == b"retain outside"
