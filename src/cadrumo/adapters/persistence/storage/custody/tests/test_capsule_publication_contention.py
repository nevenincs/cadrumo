"""Capsule publication waits out another process's handle inside the stage, and only that.

Windows refuses to rename a directory while any entry inside it is open, which
is what on-access scanning does to freshly written files. Each case holds a
real competing handle on a file inside a real stage and drives the real
by-handle rename, so the refusal and its clearing come from the kernel.
"""

from __future__ import annotations

import sys
import threading
import time
from contextlib import ExitStack
from pathlib import Path

import pytest

from .. import _capsule_filesystem
from .._capsule_filesystem import rename_windows_directory_by_handle
from ..errors import ProfileCustodyRecordError
from ..filesystem_primitives import anchor_directory

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(sys.platform != "win32", reason="the by-handle directory rename is the Windows publication"),
]

_ERROR_ACCESS_DENIED = 5
_GENERIC_READ = 0x80000000
_DELETE = 0x00010000


def _stage(root: Path) -> Path:
    stage = root / ".capsule.staging"
    stage.mkdir()
    (stage / "profile.commit.v1.json").write_bytes(b"{}")
    return stage


def test_a_handle_released_inside_the_budget_lets_the_capsule_publish(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    destination = tmp_path / "capsule"
    holder = (stage / "profile.commit.v1.json").open("rb")
    release = threading.Timer(0.3, holder.close)
    try:
        with ExitStack() as anchors:
            root_handle = anchor_directory(anchors, tmp_path, final_access=_GENERIC_READ)
            stage_handle = anchor_directory(anchors, stage, final_access=_DELETE)
            assert root_handle is not None and stage_handle is not None
            started = time.monotonic()
            release.start()
            rename_windows_directory_by_handle(stage_handle, destination, root_handle=root_handle)
            waited = time.monotonic() - started
    finally:
        release.join()
        holder.close()

    assert waited >= 0.25, "the rename succeeded while the competing handle was still open"
    assert (destination / "profile.commit.v1.json").read_bytes() == b"{}"
    assert not stage.exists()


def test_a_handle_held_past_the_budget_refuses_and_leaves_the_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_capsule_filesystem, "CAPSULE_PUBLICATION_CONTENTION_BUDGET_SECONDS", 0.2)
    stage = _stage(tmp_path)
    destination = tmp_path / "capsule"
    with (stage / "profile.commit.v1.json").open("rb"), ExitStack() as anchors:
        root_handle = anchor_directory(anchors, tmp_path, final_access=_GENERIC_READ)
        stage_handle = anchor_directory(anchors, stage, final_access=_DELETE)
        assert root_handle is not None and stage_handle is not None
        started = time.monotonic()
        with pytest.raises(
            ProfileCustodyRecordError, match=r"^atomic no-replace profile capsule publication failed$"
        ) as caught:
            rename_windows_directory_by_handle(stage_handle, destination, root_handle=root_handle)
        waited = time.monotonic() - started

    cause = caught.value.__cause__
    assert isinstance(cause, OSError)
    assert cause.errno == _ERROR_ACCESS_DENIED
    assert waited >= 0.2
    assert not destination.exists()
    assert (stage / "profile.commit.v1.json").read_bytes() == b"{}"


def test_a_refusal_that_is_not_contention_is_not_waited_on(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    destination = tmp_path / "absent-parent" / "capsule"
    with ExitStack() as anchors:
        root_handle = anchor_directory(anchors, tmp_path, final_access=_GENERIC_READ)
        stage_handle = anchor_directory(anchors, stage, final_access=_DELETE)
        assert root_handle is not None and stage_handle is not None
        started = time.monotonic()
        with pytest.raises(
            ProfileCustodyRecordError, match=r"^atomic no-replace profile capsule publication failed$"
        ) as caught:
            rename_windows_directory_by_handle(stage_handle, destination, root_handle=root_handle)
        waited = time.monotonic() - started

    cause = caught.value.__cause__
    assert isinstance(cause, OSError)
    assert cause.errno != _ERROR_ACCESS_DENIED
    assert waited < _capsule_filesystem.CAPSULE_PUBLICATION_CONTENTION_BUDGET_SECONDS / 2
    assert stage.is_dir()


def test_an_occupied_destination_is_refused_at_once_whatever_the_budget(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    destination = tmp_path / "capsule"
    destination.mkdir()
    with ExitStack() as anchors:
        root_handle = anchor_directory(anchors, tmp_path, final_access=_GENERIC_READ)
        stage_handle = anchor_directory(anchors, stage, final_access=_DELETE)
        assert root_handle is not None and stage_handle is not None
        with pytest.raises(ProfileCustodyRecordError, match=r"^profile capsule destination already exists$"):
            rename_windows_directory_by_handle(stage_handle, destination, root_handle=root_handle)

    assert stage.is_dir()
