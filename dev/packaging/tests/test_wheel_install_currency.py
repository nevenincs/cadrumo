"""Wheel currency includes deleted members and exact installer-owned additions."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from ..command_execution import run_command
from ..wheel_metadata import installed_wheel_matches

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _wheel(directory: Path, members: dict[str, bytes]) -> Path:
    directory.mkdir()
    wheel = directory / "currency_fixture-1.0-py3-none-any.whl"
    metadata = "currency_fixture-1.0.dist-info"
    members = {
        f"{metadata}/METADATA": b"Metadata-Version: 2.4\nName: currency-fixture\nVersion: 1.0\n",
        f"{metadata}/WHEEL": b"Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        **members,
    }
    record = io.StringIO(newline="")
    writer = csv.writer(record)
    for member, content in members.items():
        checksum = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
        writer.writerow((member, f"sha256={checksum}", len(content)))
    writer.writerow((f"{metadata}/RECORD", "", ""))
    with zipfile.ZipFile(wheel, "w") as archive:
        for member, content in members.items():
            archive.writestr(member, content)
        archive.writestr(f"{metadata}/RECORD", record.getvalue())
    return wheel


def _install(wheel: Path, destination: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    result = run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--reinstall",
            "--link-mode",
            "copy",
            "--target",
            str(destination),
            str(wheel),
        ],
        cwd=wheel.parent,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("removed", ["currency_fixture/obsolete.py", "currency_fixture/corpus/obsolete.pdf"])
def test_deletion_only_wheel_change_requires_reinstall_and_removes_stale_members(tmp_path: Path, removed: str) -> None:
    surviving = {"currency_fixture/__init__.py": b"answer = 42\n"}
    previous = _wheel(tmp_path / "previous", {**surviving, removed: b"obsolete"})
    current = _wheel(tmp_path / "current", surviving)
    installed = tmp_path / "dependencies"
    _install(previous, installed)
    assert installed_wheel_matches(previous, installed)
    assert not installed_wheel_matches(current, installed)
    _install(current, installed)
    assert not (installed / removed).exists()
    assert installed_wheel_matches(current, installed)


def test_installer_rows_are_allowed_but_arbitrary_extra_module_ownership_is_not(tmp_path: Path) -> None:
    wheel = _wheel(
        tmp_path / "wheel",
        {
            "currency_fixture/__init__.py": b"def main(): return 0\n",
            "currency_fixture-1.0.dist-info/entry_points.txt": (
                b"[console_scripts]\ncurrency-fixture = currency_fixture:main\n"
            ),
        },
    )
    installed = tmp_path / "dependencies"
    _install(wheel, installed)
    assert installed_wheel_matches(wheel, installed)
    record = installed / "currency_fixture-1.0.dist-info/RECORD"
    with record.open("a", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerow(("currency_fixture/unexpected.py", "", ""))
    assert not installed_wheel_matches(wheel, installed)
