"""Provisioning installs each pinned wheel once and composes the runtime tree a full install would make."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from ..provision import InstalledWheels, compose, tree_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TARGET = "windows-x86-64"


class _Installer:
    """Stands in for uv: a requirement line ``name==version`` installs ``name/__init__.py`` naming the version.

    It also writes the distribution's metadata and, for ``shared``, a file two
    distributions both install, so the order of installs decides its bytes.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, _uv: str, _target: str, _pin: str, requirements: Path, into: Path) -> None:
        for line in requirements.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            self.calls.append(line)
            name, version = line.split("==")
            (into / name).mkdir(parents=True, exist_ok=True)
            (into / name / "__init__.py").write_text(f"version = {version!r}\n", encoding="utf-8")
            (into / f"{name}-{version}.dist-info").mkdir(exist_ok=True)
            (into / f"{name}-{version}.dist-info" / "RECORD").write_text(f"{name}/__init__.py\n", encoding="utf-8")
            (into / "shared.txt").write_text(f"from {name}\n", encoding="utf-8")


def _provision(cache: Path, destination: Path, lines: list[str], installer: _Installer) -> InstalledWheels:
    installed = InstalledWheels(cache, uv="uv", target=_TARGET, pin="3.13.11", install=installer)
    if destination.exists():
        shutil.rmtree(destination)
    compose(destination, [installed.tree(line) for line in lines])
    return installed


def _full_install(destination: Path, lines: list[str]) -> None:
    """What one install of every line into one directory leaves, in order."""
    destination.mkdir(parents=True)
    installer = _Installer()
    for index, line in enumerate(lines):
        requirement = destination.parent / f"requirement-{index}.txt"
        requirement.write_text(line + "\n", encoding="utf-8")
        installer("uv", _TARGET, "3.13.11", requirement, destination)


def test_an_unchanged_wheel_keeps_its_bytes_and_file_identities(tmp_path: Path) -> None:
    cache, installer = tmp_path / "wheel-installs", _Installer()
    lines = ["alpha==1", "beta==1"]
    _provision(cache, tmp_path / "first", lines, installer)
    again = _provision(cache, tmp_path / "second", lines, installer)
    assert installer.calls == lines
    assert (again.installed, again.reused) == (0, 2)
    first = (tmp_path / "first" / "alpha" / "__init__.py").stat()
    assert (tmp_path / "second" / "alpha" / "__init__.py").stat().st_ino == first.st_ino


def test_a_changed_added_or_removed_wheel_is_reflected(tmp_path: Path) -> None:
    cache, installer = tmp_path / "wheel-installs", _Installer()
    _provision(cache, tmp_path / "first", ["alpha==1", "beta==1", "gamma==1"], installer)
    lines = ["alpha==2", "beta==1", "delta==1"]
    installed = _provision(cache, tmp_path / "second", lines, installer)
    composed = tmp_path / "second"
    assert (composed / "alpha" / "__init__.py").read_text(encoding="utf-8") == "version = '2'\n"
    assert not (composed / "alpha-1.dist-info").exists()
    assert not (composed / "gamma").exists() and not (composed / "gamma-1.dist-info").exists()
    assert (composed / "delta" / "__init__.py").is_file()
    assert (installed.installed, installed.reused) == (2, 1)
    _full_install(tmp_path / "full", lines)
    assert tree_files(composed) == tree_files(tmp_path / "full")


def test_a_later_wheel_replaces_a_file_an_earlier_one_installed(tmp_path: Path) -> None:
    lines = ["alpha==1", "beta==1"]
    _provision(tmp_path / "wheel-installs", tmp_path / "composed", lines, _Installer())
    _full_install(tmp_path / "full", lines)
    assert (tmp_path / "composed" / "shared.txt").read_text(encoding="utf-8") == "from beta\n"
    assert tree_files(tmp_path / "composed") == tree_files(tmp_path / "full")


def test_a_kept_tree_whose_files_changed_is_installed_again(tmp_path: Path) -> None:
    cache, installer = tmp_path / "wheel-installs", _Installer()
    _provision(cache, tmp_path / "first", ["alpha==1"], installer)
    # Changed through the composed link, or left half-written: either way not what was installed.
    with (tmp_path / "first" / "alpha" / "__init__.py").open("a", encoding="utf-8") as stream:
        stream.write("tampered = True\n")
    again = _provision(cache, tmp_path / "second", ["alpha==1"], installer)
    assert (again.installed, again.reused) == (1, 0)
    assert (tmp_path / "second" / "alpha" / "__init__.py").read_text(encoding="utf-8") == "version = '1'\n"
    extra = next(path for path in cache.iterdir() if path.is_dir()) / "stray.py"
    extra.write_text("stray\n", encoding="utf-8")
    third = _provision(cache, tmp_path / "third", ["alpha==1"], installer)
    assert (third.installed, third.reused) == (1, 0)
    assert not (tmp_path / "third" / "stray.py").exists()
    assert sorted(name for name in os.listdir(tmp_path / "third")) == ["alpha", "alpha-1.dist-info", "shared.txt"]
