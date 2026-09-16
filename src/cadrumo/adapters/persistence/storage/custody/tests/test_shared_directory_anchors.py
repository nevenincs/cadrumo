"""Anchors in one operation share held components without ever leaving one unheld.

These drive real directories: the property is what Windows does with a held
handle, so the rename attempts are the evidence.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from .. import filesystem_primitives
from ..capsule_discovery import anchored_current_capsule_commits
from ..filesystem_primitives import shared_directory_anchors, windows_component_paths, windows_directory_anchor
from ..paths import profile_custody_directory_name

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(os.name != "nt", reason="the Windows anchor exists only on Windows"),
]

_GENERIC_READ = 0x80000000


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Every component handle the anchors actually open."""
    recorded: list[tuple[str, int]] = []
    open_component = filesystem_primitives._open_verified_component

    def counting(current: str, access: int, **kwargs: Any) -> int:
        recorded.append((current, access))
        return open_component(current, access, **kwargs)

    monkeypatch.setattr(filesystem_primitives, "_open_verified_component", counting)
    return recorded


def test_a_nested_anchor_opens_only_what_its_parent_does_not_hold(
    tmp_path: Path,
    opened: list[tuple[str, int]],
) -> None:
    child = tmp_path / "capsules" / "member"
    child.mkdir(parents=True)

    with shared_directory_anchors(), windows_directory_anchor(child.parent, final_access=_GENERIC_READ):
        before = len(opened)
        with windows_directory_anchor(child, final_access=_GENERIC_READ):
            opened_for_child = opened[before:]

    assert opened_for_child == [(str(child), _GENERIC_READ)]
    assert len(opened) == len(windows_component_paths(child))


def test_without_a_scope_every_anchor_opens_its_whole_chain(
    tmp_path: Path,
    opened: list[tuple[str, int]],
) -> None:
    child = tmp_path / "capsules" / "member"
    child.mkdir(parents=True)

    with windows_directory_anchor(child.parent), windows_directory_anchor(child):
        pass

    assert len(opened) == len(windows_component_paths(child.parent)) + len(windows_component_paths(child))


def test_a_weaker_held_handle_never_stands_in_for_a_read_anchor(
    tmp_path: Path,
    opened: list[tuple[str, int]],
) -> None:
    """SECURITY: a final component needs its own read handle, or it could be renamed away."""
    directory = tmp_path / "capsule"
    directory.mkdir()

    with shared_directory_anchors(), ExitStack() as anchors:
        weak = anchors.enter_context(windows_directory_anchor(directory))
        before = len(opened)
        strong = anchors.enter_context(windows_directory_anchor(directory, final_access=_GENERIC_READ))

        assert opened[before:] == [(str(directory), _GENERIC_READ)]
        assert strong != weak


def test_an_ancestor_stays_held_while_any_anchor_relies_on_it(tmp_path: Path) -> None:
    """The owner leaving first does not release a component a live anchor reuses."""
    parent = tmp_path / "capsules"
    child = parent / "member"
    child.mkdir(parents=True)

    with shared_directory_anchors():
        owner = ExitStack()
        owner.enter_context(windows_directory_anchor(parent, final_access=_GENERIC_READ))
        dependant = ExitStack()
        dependant.enter_context(windows_directory_anchor(child, final_access=_GENERIC_READ))
        owner.close()

        with pytest.raises(PermissionError):
            parent.rename(tmp_path / "moved")

        dependant.close()
        parent.rename(tmp_path / "moved")


def test_a_component_is_released_when_its_last_user_leaves(tmp_path: Path) -> None:
    """Sharing never stretches a hold: an anchor that ended no longer pins anything."""
    directory = tmp_path / "capsules" / "member"
    directory.mkdir(parents=True)

    with shared_directory_anchors():
        with windows_directory_anchor(directory, final_access=_GENERIC_READ):
            pass
        (tmp_path / "capsules").rename(tmp_path / "moved-inside")
        (tmp_path / "moved-inside").rename(tmp_path / "capsules")

    (tmp_path / "capsules").rename(tmp_path / "moved-after")


@dataclass
class _Commit:
    profile_id: uuid.UUID


@pytest.fixture
def capsules_root(tmp_path: Path) -> Iterator[tuple[Path, uuid.UUID]]:
    root = tmp_path / "buckets"
    profile_id = uuid.UUID("12345678-1234-4234-8234-123456789abc")
    capsule = root / profile_custody_directory_name(profile_id)
    capsule.mkdir(parents=True)
    (capsule / "profile.commit.v1.json").write_bytes(b"{}")
    yield root, profile_id


def test_the_shared_profiles_directory_cannot_be_renamed_during_a_scan(
    tmp_path: Path,
    capsules_root: tuple[Path, uuid.UUID],
) -> None:
    """TEETH: mid-scan the capsules root is held; once the scan ends it is free."""
    root, profile_id = capsules_root
    attempts: list[bool] = []

    def parse_commit(_payload: bytes) -> _Commit:
        try:
            root.rename(tmp_path / "moved-mid-scan")
        except PermissionError:
            attempts.append(True)
        else:
            attempts.append(False)
            (tmp_path / "moved-mid-scan").rename(root)
        return _Commit(profile_id=profile_id)

    observations = anchored_current_capsule_commits(
        root,
        parse_commit=parse_commit,
        commit_filename="profile.commit.v1.json",
        maximum_bytes=1024,
    )

    assert [observation.profile_id for observation in observations] == [profile_id]
    assert attempts == [True]
    root.rename(tmp_path / "moved-after-scan")


def test_a_scan_opens_the_shared_chain_once(
    capsules_root: tuple[Path, uuid.UUID],
    opened: list[tuple[str, int]],
) -> None:
    root, profile_id = capsules_root

    anchored_current_capsule_commits(
        root,
        parse_commit=lambda _payload: _Commit(profile_id=profile_id),
        commit_filename="profile.commit.v1.json",
        maximum_bytes=1024,
        label_filename="label.json",
        label_maximum_bytes=1024,
    )

    chain = set(windows_component_paths(root.parent))
    reopened_chain = [path for path, _access in opened if path in chain]
    assert sorted(reopened_chain) == sorted(chain)
