"""A repointed storage root takes every category with it.

:func:`derived_storage_settings` isolates a test from the runner's environment;
these tests measure that a later root override moves the log and temporary
categories, through the resolver production reads.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ..core.config import override_settings
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location, storage_path
from .env_scope import derived_storage_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CATEGORIES = (StorageCategory.LOGS, StorageCategory.TEMPORARY_FILES)


def test_a_repointed_root_takes_the_log_and_temporary_categories_with_it(tmp_path: Path) -> None:
    root = tmp_path / "repointed"

    with derived_storage_settings(tmp_path / "ambient"), override_settings(cadrumo_storage_root=root):
        for category in _CATEGORIES:
            assert storage_path(category) == root / storage_location(category).relative_path()


def test_derived_storage_settings_starts_from_the_named_root(tmp_path: Path) -> None:
    ambient = tmp_path / "ambient"

    with derived_storage_settings(ambient):
        for category in _CATEGORIES:
            assert storage_path(category) == ambient / storage_location(category).relative_path()


def test_derived_storage_settings_hands_the_ambient_root_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pinned = str(tmp_path / "runner")
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", pinned)

    with derived_storage_settings(tmp_path / "ambient"):
        assert os.environ["CADRUMO_STORAGE_ROOT"] == str(tmp_path / "ambient")

    assert os.environ.get("CADRUMO_STORAGE_ROOT") == pinned
