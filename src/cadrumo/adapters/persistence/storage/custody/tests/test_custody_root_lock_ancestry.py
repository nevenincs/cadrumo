"""The custody root lock verifies its storage root once and still refuses a substituted one.

The root lock provisions the storage root and then locks a leaf inside it. The
root it provisioned stays held for the lock, so the lock's anchor stands on that
verified chain: every component is opened and verified once per acquisition, a
reparse point anywhere on the chain is still refused, and nothing is held after
the lock is released. Real directories, junctions and kernel handles; nothing
is substituted.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest

from .. import filesystem, filesystem_primitives
from ..errors import ProfileCustodyRecordError
from ..filesystem import profile_custody_root_lock
from ..filesystem_primitives import is_real_directory, windows_component_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

windows_only = pytest.mark.skipif(os.name != "nt", reason="the Windows anchor exists only on Windows")


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    """How often each component is opened; every open still runs the real verification."""
    counts: Counter[str] = Counter()
    open_component = filesystem_primitives.open_verified_component

    def counting(current: str, access: int, **kwargs: Any) -> int:
        counts[current] += 1
        return open_component(current, access, **kwargs)

    monkeypatch.setattr(filesystem_primitives, "open_verified_component", counting)
    return counts


def _create_junction(target: Path, link: Path) -> None:
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return
    pytest.fail("junctions exist only on Windows")


@windows_only
def test_one_acquisition_opens_each_storage_root_component_once(tmp_path: Path, opened: Counter[str]) -> None:
    root = tmp_path / "storage"
    root.mkdir()

    with profile_custody_root_lock(root):
        pass

    assert opened == Counter(windows_component_paths(root))


@windows_only
def test_an_absent_storage_root_is_provisioned_once_and_locked(tmp_path: Path, opened: Counter[str]) -> None:
    root = tmp_path / "storage"

    with profile_custody_root_lock(root):
        assert is_real_directory(root)

    assert opened == Counter(windows_component_paths(root))


@windows_only
def test_a_storage_root_that_is_a_junction_is_refused(tmp_path: Path) -> None:
    """SECURITY: holding the provisioned root never lets the lock stand on a reparse point."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    root = tmp_path / "storage"
    _create_junction(elsewhere, root)

    with pytest.raises(ProfileCustodyRecordError), profile_custody_root_lock(root):
        pass

    assert list(elsewhere.iterdir()) == []


@windows_only
def test_a_storage_root_below_a_junction_is_refused(tmp_path: Path) -> None:
    """SECURITY: every ancestor of the root is verified, not only the root itself."""
    real_parent = tmp_path / "real-parent"
    (real_parent / "storage").mkdir(parents=True)
    linked_parent = tmp_path / "linked-parent"
    _create_junction(real_parent, linked_parent)

    with pytest.raises(ProfileCustodyRecordError), profile_custody_root_lock(linked_parent / "storage"):
        pass

    assert list((real_parent / "storage").iterdir()) == []


@windows_only
def test_the_storage_root_is_pinned_while_locked_and_free_after(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir()

    with profile_custody_root_lock(root), pytest.raises(PermissionError):
        root.rename(tmp_path / "moved-inside")

    root.rename(tmp_path / "moved-after")


def test_a_re_entered_root_lock_provisions_nothing_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "storage"
    provisioned: list[Path] = []
    hold = filesystem_primitives.hold_profile_custody_local_directory

    def recording(stack: ExitStack, path: Path) -> None:
        provisioned.append(path)
        hold(stack, path)

    monkeypatch.setattr(filesystem, "hold_profile_custody_local_directory", recording)
    with profile_custody_root_lock(root), profile_custody_root_lock(root):
        pass

    assert provisioned == [root]
