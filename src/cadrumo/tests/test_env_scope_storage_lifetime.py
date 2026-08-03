"""The temporary storage roots ``env_scope`` mints do not outlive the session.

``settings_without_env_file`` mints a temporary root whenever the caller
supplies none and the environment carries none, and holds it open because the
returned :class:`Settings` names that path. Holding it open is correct;
holding it forever was not. A runtime write census measured 457 of them in the
operator's temp directory, the oldest three weeks old -- one per call, across
every session ever run, covered by no sweep.

These pin the lifetime rather than the mechanism: that a root is created and
usable while it is needed, and gone once released.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .env_scope import (
    _SETTINGS_STORAGE_DIRECTORIES,
    isolated_aeat_env,
    release_settings_storage_directories,
    settings_without_env_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_minted_root_exists_while_it_is_held() -> None:
    """The directory is real while the Settings that names it is in use.

    The positive control for every assertion below: releasing something that
    was never created would satisfy a removal check trivially.
    """
    with isolated_aeat_env():
        settings = settings_without_env_file()
        root = Path(settings.cadrumo_local_storage_root)

        assert root.is_dir()
        assert root.name.startswith("cadrumo-settings-")
        assert _SETTINGS_STORAGE_DIRECTORIES, "the mint must be tracked, or nothing can release it"

    release_settings_storage_directories()


def test_release_removes_every_minted_root() -> None:
    """After release the directories are gone and nothing is still tracked."""
    with isolated_aeat_env():
        roots = [Path(settings_without_env_file().cadrumo_local_storage_root) for _ in range(3)]

    assert len(set(roots)) == 3, "each call must mint its own root, or isolation is shared"
    assert all(root.is_dir() for root in roots)

    release_settings_storage_directories()

    assert not any(root.exists() for root in roots), f"still on disk: {[r for r in roots if r.exists()]}"
    assert not _SETTINGS_STORAGE_DIRECTORIES


def test_release_is_safe_to_repeat_and_safe_when_nothing_was_minted() -> None:
    """Session teardown must not depend on whether any root was minted.

    The fixture runs for every session, including ones that never call the
    factory, and a teardown that raised there would fail sessions unrelated to
    the thing being cleaned up.
    """
    release_settings_storage_directories()
    release_settings_storage_directories()

    assert not _SETTINGS_STORAGE_DIRECTORIES


def test_a_caller_supplied_root_is_not_minted_or_released(tmp_path: Path) -> None:
    """Only roots this module created are its to remove.

    The guard that matters for a destructive teardown: a caller that names its
    own storage root owns that directory, and release must not reach it.
    """
    supplied = tmp_path / "operator-owned"
    supplied.mkdir()

    with isolated_aeat_env():
        settings = settings_without_env_file(cadrumo_local_storage_root=supplied)

    assert Path(settings.cadrumo_local_storage_root) == supplied
    assert not _SETTINGS_STORAGE_DIRECTORIES, "a supplied root must not be tracked for removal"

    release_settings_storage_directories()

    assert supplied.is_dir(), "release deleted a directory it did not create"
