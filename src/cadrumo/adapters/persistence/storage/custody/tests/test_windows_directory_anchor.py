"""The Windows directory anchor pins the directory that exists NOW, per operation.

The anchor is a held lock, not a computed value: each call opens every path
component without delete sharing and keeps the handles for the operation. These
cases drive real directories, because the property is what the filesystem does
with a held handle, which no constructed fixture can stand in for.
"""

from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path

import pytest

from ..errors import ProfileCustodyRecordError
from ..filesystem_primitives import (
    anchor_directory,
    windows_component_paths,
    windows_create_file_api,
    windows_directory_anchor,
    windows_file_information_type,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(os.name != "nt", reason="the Windows anchor exists only on Windows"),
]

_GENERIC_READ = 0x80000000


def _identity(handle: int) -> tuple[int, int, int]:
    ctypes, _wintypes, kernel32, _create_file = windows_create_file_api()
    info = windows_file_information_type()()
    assert kernel32.GetFileInformationByHandle(handle, ctypes.byref(info))
    return int(info.dwVolumeSerialNumber), int(info.nFileIndexHigh), int(info.nFileIndexLow)


def _pathlib_component_paths(path: Path) -> list[str]:
    current = Path(path.anchor)
    rendered: list[str] = []
    for component in path.parts[1:] if path.anchor else path.parts:
        current /= component
        rendered.append(str(current))
    return rendered


@pytest.mark.parametrize(
    "raw",
    [
        "C:\\Users\\operator\\storage",
        "\\\\server\\share\\capsules\\bucket",
        "relative\\capsules\\bucket",
        "C:relative\\bucket",
        "D:\\a",
        "C:\\",
    ],
)
def test_component_paths_match_the_pathlib_rendering(raw: str) -> None:
    """The string walk opens exactly the paths the pathlib walk opened."""
    path = Path(raw)

    assert list(windows_component_paths(path)) == _pathlib_component_paths(path)


def test_a_replaced_directory_is_anchored_as_the_new_directory(tmp_path: Path) -> None:
    """Anchoring after a rename-away and recreate pins the replacement, not the original."""
    directory = tmp_path / "capsule"
    directory.mkdir()
    with windows_directory_anchor(directory) as handle:
        original = _identity(handle)

    directory.rename(tmp_path / "retired")
    directory.mkdir()
    with windows_directory_anchor(directory) as handle:
        replacement = _identity(handle)

    assert replacement != original


def test_a_held_read_anchor_refuses_renaming_the_directory_away(tmp_path: Path) -> None:
    """While an operation holds a read anchor, the directory cannot be substituted.

    Only a handle with data access takes part in Windows share-mode checks, so
    this pins the final directory when opened for read, as custody directory
    creation does. The lock ends with the operation: the same rename succeeds
    once the anchor is released.
    """
    directory = tmp_path / "capsule"
    directory.mkdir()
    with ExitStack() as anchors:
        anchor_directory(anchors, directory, final_access=_GENERIC_READ)
        with pytest.raises(PermissionError):
            directory.rename(tmp_path / "retired")

    directory.rename(tmp_path / "retired")


def test_a_held_anchor_refuses_renaming_a_parent_away(tmp_path: Path) -> None:
    """Every component above the anchored directory is pinned for the operation."""
    parent = tmp_path / "bucket"
    directory = parent / "capsule"
    directory.mkdir(parents=True)
    with ExitStack() as anchors:
        anchor_directory(anchors, directory)
        with pytest.raises(PermissionError):
            parent.rename(tmp_path / "retired")

    parent.rename(tmp_path / "retired")


def test_anchoring_a_file_is_refused(tmp_path: Path) -> None:
    """A non-directory component is refused rather than pinned."""
    member = tmp_path / "member.json"
    member.write_bytes(b"{}")

    with pytest.raises(ProfileCustodyRecordError), windows_directory_anchor(member):
        pass
