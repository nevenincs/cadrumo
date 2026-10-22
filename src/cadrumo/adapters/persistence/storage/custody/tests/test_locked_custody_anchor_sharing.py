"""A locked custody operation verifies the storage ancestry once and still refuses links below it.

The lock holds every component of its parent for the whole locked body, so an
anchor inside stands on those held handles. These cases drive real directories,
junctions and threads: the guarantees are what Windows does with held handles.
"""

from __future__ import annotations

import contextvars
import os
import sys
import threading
from collections.abc import Callable
from contextlib import ExitStack
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from .. import filesystem_primitives
from ..errors import ProfileCustodyRecordError
from ..filesystem import profile_custody_local_lock
from ..filesystem_primitives import (
    ensure_profile_custody_local_directory,
    is_real_directory,
    shared_directory_anchors,
    windows_component_paths,
    windows_directory_anchor,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

windows_only = pytest.mark.skipif(os.name != "nt", reason="the Windows anchor exists only on Windows")

_GENERIC_READ = 0x80000000
_DELETE = 0x00010000


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Every component handle the anchors actually open; each open still runs the real verification."""
    recorded: list[tuple[str, int]] = []
    open_component = filesystem_primitives._open_verified_component

    def counting(current: str, access: int, **kwargs: Any) -> int:
        recorded.append((current, access))
        return open_component(current, access, **kwargs)

    monkeypatch.setattr(filesystem_primitives, "_open_verified_component", counting)
    return recorded


def _create_junction(target: Path, link: Path) -> None:
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return
    pytest.fail("junctions exist only on Windows")


@windows_only
def test_anchors_inside_a_lock_open_only_what_lies_below_its_parent(
    tmp_path: Path,
    opened: list[tuple[str, int]],
) -> None:
    root = tmp_path / "storage"
    member = root / "automation" / "profile"
    member.mkdir(parents=True)

    with profile_custody_local_lock(root / ".custody.lock"):
        before = len(opened)
        for _ in range(3):
            with windows_directory_anchor(member, final_access=_GENERIC_READ):
                pass
        inside = opened[before:]

    below = [str(root / "automation"), str(member)]
    assert [path for path, _access in inside] == below * 3


@windows_only
def test_the_ancestry_a_lock_shares_stays_pinned_for_the_body_and_is_free_after(tmp_path: Path) -> None:
    """Reusing the lock's handles never releases them early and never keeps them past the lock."""
    root = tmp_path / "storage"
    member = root / "member"
    member.mkdir(parents=True)

    with profile_custody_local_lock(root / ".custody.lock"):
        with windows_directory_anchor(member, final_access=_GENERIC_READ):
            pass
        with pytest.raises(PermissionError):
            root.rename(tmp_path / "moved-inside")

    root.rename(tmp_path / "moved-after")


@windows_only
@pytest.mark.parametrize("swapped", ["parent", "leaf"])
def test_a_component_swapped_for_a_junction_between_anchors_in_one_lock_is_refused(
    tmp_path: Path,
    swapped: str,
) -> None:
    """SECURITY: a component below the lock's parent is verified again by every anchor that reaches it."""
    root = tmp_path / "storage"
    leaf = root / "automation" / "profile"
    leaf.mkdir(parents=True)
    target = leaf.parent if swapped == "parent" else leaf
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "profile").mkdir(parents=True)

    with profile_custody_local_lock(root / ".custody.lock"):
        with windows_directory_anchor(leaf, final_access=_GENERIC_READ):
            pass
        target.rename(target.with_name("retired"))
        _create_junction(elsewhere if swapped == "parent" else elsewhere / "profile", target)

        with pytest.raises(ProfileCustodyRecordError), windows_directory_anchor(leaf, final_access=_GENERIC_READ):
            pass


@windows_only
def test_a_thread_carrying_the_operation_context_anchors_alone(
    tmp_path: Path,
    opened: list[tuple[str, int]],
) -> None:
    """A copied context does not let another thread stand on, or release, this thread's handles."""
    member = tmp_path / "storage" / "member"
    member.mkdir(parents=True)
    failures: list[BaseException] = []

    def anchor_member() -> None:
        try:
            with windows_directory_anchor(member, final_access=_GENERIC_READ):
                pass
        except BaseException as exc:  # handed to the test thread, which re-raises it
            failures.append(exc)

    with shared_directory_anchors(), windows_directory_anchor(member, final_access=_GENERIC_READ):
        before = len(opened)
        worker = threading.Thread(target=contextvars.copy_context().run, args=(anchor_member,))
        worker.start()
        worker.join()
        opened_by_worker = opened[before:]

        with pytest.raises(PermissionError):
            member.rename(member.with_name("moved"))

    assert failures == []
    assert [path for path, _access in opened_by_worker] == list(windows_component_paths(member))


@windows_only
def test_a_handle_that_can_move_its_directory_is_never_stood_on_by_another_anchor(
    tmp_path: Path,
    opened: list[tuple[str, int]],
) -> None:
    """SECURITY: once moved, a delete-capable handle no longer names the path it would be shared under."""
    stage = tmp_path / "stage"
    child = stage / "custody"
    child.mkdir(parents=True)

    with shared_directory_anchors(), ExitStack() as anchors:
        anchors.enter_context(windows_directory_anchor(stage, final_access=_DELETE))
        before = len(opened)
        anchors.enter_context(windows_directory_anchor(child, final_access=_GENERIC_READ))

        assert opened[before:] == [(str(stage), 0), (str(child), _GENERIC_READ)]


@cache
def _mkdir_recorder() -> list[list[str]]:
    """Install one process-wide audit hook; a test records only while it holds a slot."""
    slots: list[list[str]] = []

    def record(event: str, arguments: tuple[object, ...]) -> None:
        if event == "os.mkdir" and slots and isinstance(arguments[0], (str, bytes, os.PathLike)):
            slots[-1].append(os.path.basename(os.fsdecode(arguments[0])))

    sys.addaudithook(record)
    return slots


def _mkdirs_during(action: Callable[[], None]) -> list[str]:
    slots = _mkdir_recorder()
    recorded: list[str] = []
    slots.append(recorded)
    try:
        action()
    finally:
        slots.remove(recorded)
    return recorded


def test_an_existing_custody_directory_is_not_created_again(tmp_path: Path) -> None:
    directory = tmp_path / "custody"
    directory.mkdir()

    assert _mkdirs_during(lambda: ensure_profile_custody_local_directory(directory)) == []
    assert is_real_directory(directory)


def test_an_absent_custody_directory_is_created_as_a_real_directory(tmp_path: Path) -> None:
    directory = tmp_path / "custody"

    assert _mkdirs_during(lambda: ensure_profile_custody_local_directory(directory)) == ["custody"]
    assert is_real_directory(directory)


def test_a_link_standing_where_a_custody_directory_belongs_is_refused(tmp_path: Path) -> None:
    """SECURITY: finding the name taken spares the creation, never the verification."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    directory = tmp_path / "custody"
    if os.name == "nt":
        _create_junction(elsewhere, directory)
    else:
        directory.symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(ProfileCustodyRecordError):
        ensure_profile_custody_local_directory(directory)
