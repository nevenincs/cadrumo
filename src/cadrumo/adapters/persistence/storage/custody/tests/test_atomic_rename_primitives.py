"""Descriptor-relative atomic renames select the host's documented call and refuse replacement.

The selection and errno classification are checked on every host. The native
cases drive the real libc call on hosts that have one: a plain ``rename``
would silently replace each refused destination below, so those refusals are
the evidence that the no-replace flag reached the kernel.
"""

from __future__ import annotations

import errno
import os
import sys
from pathlib import Path

import pytest

from ..errors import ProfileCustodyRecordError
from ..filesystem_primitives import (
    NativeAtomicRename,
    native_atomic_rename,
    posix_directory_fd,
    raise_rename_noreplace_failure,
    rename_exchange_at,
    rename_noreplace_at,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NATIVE = native_atomic_rename(sys.platform, exchange=False) is not None
_requires_native = pytest.mark.skipif(not _NATIVE, reason="the host has no descriptor-relative atomic rename")


@pytest.mark.parametrize(
    ("platform", "exchange", "expected"),
    [
        # linux/fs.h: RENAME_NOREPLACE (1 << 0), RENAME_EXCHANGE (1 << 1).
        pytest.param("linux", False, NativeAtomicRename(symbol="renameat2", flags=0x1), id="linux-noreplace"),
        pytest.param("linux", True, NativeAtomicRename(symbol="renameat2", flags=0x2), id="linux-exchange"),
        # Darwin sys/stdio.h: RENAME_SWAP 0x00000002, RENAME_EXCL 0x00000004.
        pytest.param("darwin", False, NativeAtomicRename(symbol="renameatx_np", flags=0x4), id="darwin-excl"),
        pytest.param("darwin", True, NativeAtomicRename(symbol="renameatx_np", flags=0x2), id="darwin-swap"),
    ],
)
def test_each_supported_host_selects_its_documented_call_and_flag(
    platform: str, exchange: bool, expected: NativeAtomicRename
) -> None:
    assert native_atomic_rename(platform, exchange=exchange) == expected


@pytest.mark.parametrize("platform", ["win32", "cygwin", "freebsd14", "openbsd7", "aix", "emscripten"])
def test_hosts_without_a_descriptor_relative_atomic_rename_select_nothing(platform: str) -> None:
    assert native_atomic_rename(platform, exchange=False) is None
    assert native_atomic_rename(platform, exchange=True) is None


@pytest.mark.parametrize("error", [errno.EEXIST, errno.ENOTEMPTY])
def test_an_occupied_destination_is_refused_as_already_existing(error: int) -> None:
    with pytest.raises(ProfileCustodyRecordError, match=r"^profile capsule destination already exists$") as caught:
        raise_rename_noreplace_failure(error)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("error", [errno.ENOENT, errno.EXDEV, errno.EACCES, errno.EINVAL])
def test_any_other_rename_failure_keeps_its_native_errno(error: int) -> None:
    with pytest.raises(
        ProfileCustodyRecordError, match=r"^atomic no-replace profile capsule publication failed$"
    ) as caught:
        raise_rename_noreplace_failure(error)
    cause = caught.value.__cause__
    assert isinstance(cause, OSError)
    assert cause.errno == error


@pytest.mark.skipif(_NATIVE, reason="the host has a descriptor-relative atomic rename")
def test_a_host_without_an_atomic_rename_refuses_before_any_native_call() -> None:
    with pytest.raises(
        ProfileCustodyRecordError, match=r"^atomic no-replace profile capsule publication is unavailable$"
    ):
        rename_noreplace_at(source_fd=-1, source_name="source", destination_fd=-1, destination_name="destination")
    with pytest.raises(ProfileCustodyRecordError, match=r"^atomic local custody record exchange is unavailable$"):
        rename_exchange_at(parent_fd=-1, first_name="first", second_name="second")


@_requires_native
def test_noreplace_renames_into_an_absent_destination(tmp_path: Path) -> None:
    (tmp_path / "source").write_bytes(b"payload")
    with posix_directory_fd(tmp_path) as parent_fd:
        rename_noreplace_at(
            source_fd=parent_fd, source_name="source", destination_fd=parent_fd, destination_name="destination"
        )
    assert not (tmp_path / "source").exists()
    assert (tmp_path / "destination").read_bytes() == b"payload"


@_requires_native
def test_noreplace_refuses_an_existing_file_and_leaves_both_unchanged(tmp_path: Path) -> None:
    (tmp_path / "source").write_bytes(b"incoming")
    (tmp_path / "destination").write_bytes(b"resident")
    with (
        posix_directory_fd(tmp_path) as parent_fd,
        pytest.raises(ProfileCustodyRecordError, match=r"^profile capsule destination already exists$"),
    ):
        rename_noreplace_at(
            source_fd=parent_fd, source_name="source", destination_fd=parent_fd, destination_name="destination"
        )
    assert (tmp_path / "source").read_bytes() == b"incoming"
    assert (tmp_path / "destination").read_bytes() == b"resident"


@_requires_native
@pytest.mark.parametrize("occupied", [False, True], ids=["empty", "non-empty"])
def test_noreplace_refuses_an_existing_directory(tmp_path: Path, occupied: bool) -> None:
    (tmp_path / "stage").mkdir()
    (tmp_path / "stage" / "commit").write_bytes(b"staged")
    (tmp_path / "published").mkdir()
    if occupied:
        (tmp_path / "published" / "commit").write_bytes(b"published")
    with (
        posix_directory_fd(tmp_path) as parent_fd,
        pytest.raises(ProfileCustodyRecordError, match=r"^profile capsule destination already exists$"),
    ):
        rename_noreplace_at(
            source_fd=parent_fd, source_name="stage", destination_fd=parent_fd, destination_name="published"
        )
    assert (tmp_path / "stage" / "commit").read_bytes() == b"staged"
    assert [entry.name for entry in (tmp_path / "published").iterdir()] == (["commit"] if occupied else [])


@_requires_native
def test_noreplace_reports_a_missing_source_with_its_native_errno(tmp_path: Path) -> None:
    with (
        posix_directory_fd(tmp_path) as parent_fd,
        pytest.raises(ProfileCustodyRecordError, match="publication failed") as caught,
    ):
        rename_noreplace_at(
            source_fd=parent_fd, source_name="absent", destination_fd=parent_fd, destination_name="destination"
        )
    cause = caught.value.__cause__
    assert isinstance(cause, OSError)
    assert cause.errno == errno.ENOENT
    assert not (tmp_path / "destination").exists()


@_requires_native
def test_exchange_swaps_two_names_and_their_inodes(tmp_path: Path) -> None:
    (tmp_path / "current").write_bytes(b"current")
    (tmp_path / "replacement").write_bytes(b"replacement")
    current_inode = os.stat(tmp_path / "current").st_ino
    replacement_inode = os.stat(tmp_path / "replacement").st_ino
    with posix_directory_fd(tmp_path) as parent_fd:
        rename_exchange_at(parent_fd=parent_fd, first_name="current", second_name="replacement")
    assert (tmp_path / "current").read_bytes() == b"replacement"
    assert (tmp_path / "replacement").read_bytes() == b"current"
    assert os.stat(tmp_path / "current").st_ino == replacement_inode
    assert os.stat(tmp_path / "replacement").st_ino == current_inode


@_requires_native
def test_exchange_refuses_a_missing_name_without_creating_it(tmp_path: Path) -> None:
    (tmp_path / "current").write_bytes(b"current")
    with (
        posix_directory_fd(tmp_path) as parent_fd,
        pytest.raises(ProfileCustodyRecordError, match=r"^atomic local custody record exchange failed$") as caught,
    ):
        rename_exchange_at(parent_fd=parent_fd, first_name="current", second_name="absent")
    cause = caught.value.__cause__
    assert isinstance(cause, OSError)
    assert cause.errno == errno.ENOENT
    assert (tmp_path / "current").read_bytes() == b"current"
    assert not (tmp_path / "absent").exists()
