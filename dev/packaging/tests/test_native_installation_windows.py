"""Real Windows handle deletion refuses intervening edits and namespace replacement."""

from __future__ import annotations

import hashlib
import os
import sys
from io import BufferedReader
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from dev.packaging.command_execution import run_command
from dev.packaging.native import installation_windows
from dev.packaging.native.hashing import digest
from dev.packaging.native.installation_windows import remove_windows_owned_file

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_core,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="Requires real Windows retained file handles"),
]


def _owned_file(tmp_path: Path) -> tuple[Path, str, tuple[int, int]]:
    parent = tmp_path / "installed"
    parent.mkdir()
    path = parent / "owned.bin"
    path.write_bytes(b"receipt-owned native program bytes")
    metadata = path.lstat()
    return path, digest(path), (metadata.st_dev, metadata.st_ino)


def test_exact_unchanged_handle_removal_closes_and_releases_ancestry(tmp_path: Path) -> None:
    path, checksum, expected = _owned_file(tmp_path)
    assert remove_windows_owned_file(path, checksum, expected)
    assert not path.exists()
    path.parent.rename(tmp_path / "released-parent")


def test_already_absent_member_is_success_without_touching_other_files(tmp_path: Path) -> None:
    path, checksum, expected = _owned_file(tmp_path)
    path.unlink()
    sentinel = path.parent / "unowned.bin"
    sentinel.write_bytes(b"unowned bytes")
    assert remove_windows_owned_file(path, checksum, expected)
    assert sentinel.read_bytes() == b"unowned bytes"


def test_intervening_edit_is_preserved_and_handle_is_released(tmp_path: Path) -> None:
    path, checksum, expected = _owned_file(tmp_path)
    path.write_bytes(b"operator modification after preflight")
    assert not remove_windows_owned_file(path, checksum, expected)
    assert path.read_bytes() == b"operator modification after preflight"
    path.rename(path.with_name("preserved.bin"))


def test_identical_bytes_at_replaced_identity_are_preserved(tmp_path: Path) -> None:
    path, checksum, expected = _owned_file(tmp_path)
    original = path.with_name("original-retained.bin")
    path.rename(original)
    path.write_bytes(original.read_bytes())
    observed = path.lstat()
    assert (observed.st_dev, observed.st_ino) != expected
    assert not remove_windows_owned_file(path, checksum, expected)
    assert path.read_bytes() == original.read_bytes()


def test_directory_at_file_name_is_refused_without_deletion(tmp_path: Path) -> None:
    path, checksum, expected = _owned_file(tmp_path)
    path.rename(path.with_name("original-retained.bin"))
    path.mkdir()
    sentinel = path / "unowned.bin"
    sentinel.write_bytes(b"foreign directory contents")
    with pytest.raises((OSError, ValueError)):
        remove_windows_owned_file(path, checksum, expected)
    assert sentinel.read_bytes() == b"foreign directory contents"


def test_intervening_parent_junction_cannot_redirect_deletion(tmp_path: Path) -> None:
    path, checksum, expected = _owned_file(tmp_path)
    original_parent = tmp_path / "original-parent"
    path.parent.rename(original_parent)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    foreign_file = foreign / path.name
    foreign_file.write_bytes((original_parent / path.name).read_bytes())
    command = Path(os.environ["SYSTEMROOT"]) / "System32" / "cmd.exe"
    result = run_command(
        [str(command), "/d", "/c", "mklink", "/J", str(path.parent), str(foreign)],
        cwd=tmp_path,
        timeout_seconds=10,
    )
    assert result.returncode == 0, result.stderr
    assert path.parent.is_junction()
    with pytest.raises((OSError, ValueError, ProfileCustodyRecordError)):
        remove_windows_owned_file(path, checksum, expected)
    assert foreign_file.read_bytes() == b"receipt-owned native program bytes"
    assert (original_parent / path.name).read_bytes() == foreign_file.read_bytes()


def test_existing_nonsharing_reader_refuses_without_mutating_file(tmp_path: Path) -> None:
    path, checksum, expected = _owned_file(tmp_path)
    with path.open("rb") as reader:
        with pytest.raises(OSError):
            remove_windows_owned_file(path, checksum, expected)
        assert reader.read() == b"receipt-owned native program bytes"
    assert remove_windows_owned_file(path, checksum, expected)


def test_hashing_retains_file_and_parent_against_writes_and_replacements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, checksum, expected = _owned_file(tmp_path)
    replacement = tmp_path / "replacement.bin"
    replacement.write_bytes(b"unowned replacement")
    file_digest = hashlib.file_digest
    guarded = False

    def guarded_digest(stream: BufferedReader, algorithm: str) -> object:
        nonlocal guarded
        guarded = True
        with pytest.raises(PermissionError):
            path.write_bytes(b"attempted edit")
        with pytest.raises(PermissionError):
            replacement.replace(path)
        with pytest.raises(PermissionError):
            path.parent.rename(tmp_path / "replacement-parent")
        assert replacement.read_bytes() == b"unowned replacement"
        return file_digest(stream, algorithm)

    monkeypatch.setattr(installation_windows.hashlib, "file_digest", guarded_digest)
    assert remove_windows_owned_file(path, checksum, expected)
    assert guarded, "The exact retained handle was never verified"
    assert not path.exists()
    assert replacement.read_bytes() == b"unowned replacement"
    path.parent.rename(tmp_path / "released-parent")
