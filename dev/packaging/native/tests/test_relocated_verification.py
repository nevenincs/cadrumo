"""Already extracted artifacts are admitted in place, never materialized twice."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...command_execution import CommandResult
from ..layout import load_layout
from ..platforms import posix, windows_verify
from ..verification_paths import relocated_verification_package

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_relocated_package_is_admitted_only_inside_its_owner(tmp_path: Path) -> None:
    owner = tmp_path / "verification"
    package = owner / "ZIP espacio á 漢字/app"
    package.mkdir(parents=True)
    assert relocated_verification_package(package, owner) == package.resolve()
    with pytest.raises(ValueError, match="beneath its owning build root"):
        relocated_verification_package(owner, owner)
    outside = tmp_path / "installed"
    outside.mkdir()
    with pytest.raises(ValueError, match="beneath its owning build root"):
        relocated_verification_package(outside, owner)


def test_relocated_package_refuses_linked_directory_aliases(tmp_path: Path) -> None:
    owner = tmp_path / "verification"
    package = owner / "actual/app"
    package.mkdir(parents=True)
    link = owner / "linked"
    try:
        link.symlink_to(package.parent, target_is_directory=True)
    except OSError:
        pytest.skip("This host cannot create directory links")
    with pytest.raises(ValueError, match="linked directories"):
        relocated_verification_package(link / "app", owner)


def test_windows_acceptance_reaches_existing_executable_without_copying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "ZIP espacio á 漢字/app"
    data = package / "data"
    data.mkdir(parents=True)
    (data / "package-manifest.json").write_text(json.dumps({"layout": {}}))
    executable = package / "python.exe"
    executable.write_bytes(b"native fixture intentionally not executable")
    original_files = {path.relative_to(package): path.read_bytes() for path in package.rglob("*") if path.is_file()}

    def copy_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("A second materialization was attempted")

    def reached_native_probe(argv: list[str], **kwargs: object) -> None:
        assert argv[0] == str(executable.resolve())
        assert kwargs["cwd"] == tmp_path / "acceptance unrelated cwd"
        raise RuntimeError("existing native probe reached; fixture has no executable")

    monkeypatch.setattr(windows_verify.shutil, "copytree", copy_forbidden)
    monkeypatch.setattr(windows_verify, "run_command", reached_native_probe)
    with pytest.raises(RuntimeError, match="existing native probe reached"):
        windows_verify.verify(package, build_root=tmp_path, already_relocated=True)
    assert original_files == {
        path.relative_to(package): path.read_bytes() for path in package.rglob("*") if path.is_file()
    }


def test_posix_acceptance_preserves_one_extraction_through_refusal_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = load_layout("linux-x86-64")
    package = tmp_path / "ZIP espacio á 漢字/app"
    manifest = package / layout["files"]["package_manifest"]
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"layout": layout, "smoke_modules": {"core": ["json"]}}))
    executable = package / layout["paths"]["executable"]
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"fixture interpreter")
    runtime = package / layout["paths"]["native"] / layout["files"]["runtime"]
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_bytes(b"original runtime")
    original_files = {path.relative_to(package): path.read_bytes() for path in package.rglob("*") if path.is_file()}
    refusals = []

    def copy_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("A second materialization was attempted")

    def native_probe(argv: list[str], *, environment: dict[str, str], cwd: Path, timeout_seconds: int) -> CommandResult:
        assert argv[0] == str(executable.resolve())
        assert not cwd.is_relative_to(package)
        refusal = (
            "hostile"
            if "LD_LIBRARY_PATH" in environment
            else "missing"
            if not runtime.exists()
            else "damaged"
            if runtime.read_bytes() != b"original runtime"
            else ""
        )
        if refusal:
            refusals.append(refusal)
        now = datetime.now(UTC)
        return CommandResult(tuple(argv), str(cwd), now, now, 0, int(bool(refusal)), "{}", "cannot load bundled")

    monkeypatch.setattr(posix.sys, "platform", "linux")
    monkeypatch.setattr(posix.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(posix.shutil, "copytree", copy_forbidden)
    monkeypatch.setattr(posix, "run_command", native_probe)
    posix.verify_package(package, tmp_path, "linux", already_relocated=True)
    assert refusals == ["hostile", "missing", "damaged"]
    assert original_files == {
        path.relative_to(package): path.read_bytes() for path in package.rglob("*") if path.is_file()
    }
    result = json.loads((tmp_path / "native-verification.json").read_text())
    assert result["relocated"] == str(package.resolve())
    assert result["package_immutable"]
