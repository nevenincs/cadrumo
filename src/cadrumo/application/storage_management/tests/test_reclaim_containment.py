"""Containment proof for taxonomy-derived area reclaim targets."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ....core import STORAGE_TAXONOMY, StorageArea, StorageScope, storage_path
from ....core.config import override_settings
from .._service import RECLAIMABLE_LIFECYCLES, reclaim_storage_area
from ..errors import StorageReclaimRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _targets(area: StorageArea):
    return tuple(
        category
        for category, location in STORAGE_TAXONOMY.items()
        if location.grouping.value == area.value
        and location.scope is StorageScope.ROOT
        and location.lifecycle in RECLAIMABLE_LIFECYCLES
    )


def _bind_directory(link: Path, target: Path) -> str:
    """Bind ``link`` to ``target`` with the platform's ordinary mechanism."""
    if sys.platform == "win32":
        import _winapi

        create_junction = getattr(_winapi, "CreateJunction", None)
        if create_junction is None:  # pragma: no cover - absent only on non-CPython builds
            raise RuntimeError("this Windows runtime cannot create a junction")
        create_junction(str(target), str(link))
        return "junction"
    os.symlink(target, link, target_is_directory=True)
    return "symlink"


class TestDerivedPreflight:
    @pytest.mark.parametrize("area", [StorageArea.LOGS, StorageArea.CACHE])
    def test_every_selected_target_is_root_scoped_and_reclaimable(self, area: StorageArea) -> None:
        selected = _targets(area)
        assert selected
        for category in selected:
            location = STORAGE_TAXONOMY[category]
            assert location.scope is StorageScope.ROOT
            assert location.lifecycle in RECLAIMABLE_LIFECYCLES

    @pytest.mark.parametrize("area", [StorageArea.LOGS, StorageArea.CACHE])
    def test_no_selected_target_contains_a_protected_declared_descendant(self, area: StorageArea, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            selected = {category: storage_path(category) for category in _targets(area)}
            protected = {
                category: storage_path(category)
                for category, location in STORAGE_TAXONOMY.items()
                if location.scope is StorageScope.ROOT and location.lifecycle not in RECLAIMABLE_LIFECYCLES
            }

        assert selected
        for selected_path in selected.values():
            assert not [path for path in protected.values() if path.is_relative_to(selected_path)]


class TestFilesystemContainment:
    def test_reclaim_does_not_follow_a_link_outside_its_target(self, tmp_path) -> None:
        category = _targets(StorageArea.CACHE)[0]
        with override_settings(cadrumo_local_storage_root=tmp_path / "storage"):
            target = storage_path(category)
            target.mkdir(parents=True, exist_ok=True)
            outside = tmp_path / "outside"
            outside.mkdir()
            survivor = outside / "taxpayer-evidence.bin"
            survivor.write_bytes(b"survive")
            link = target / "outside-link"
            link_kind = _bind_directory(link, outside)
            ordinary = target / "ordinary.bin"
            ordinary.write_bytes(b"delete")

            report = reclaim_storage_area(StorageArea.CACHE, confirmed=True)

        assert report.removed_entries >= 2
        assert not ordinary.exists()
        assert not os.path.lexists(link)
        assert survivor.read_bytes() == b"survive", f"external target lost through {link_kind}"

    def test_reclaim_refuses_a_declared_target_redirected_outside_storage(self, tmp_path) -> None:
        redirected_category, ordinary_category = _targets(StorageArea.CACHE)
        with override_settings(cadrumo_local_storage_root=tmp_path / "storage"):
            redirected_target = storage_path(redirected_category)
            redirected_target.parent.mkdir(parents=True, exist_ok=True)
            outside = tmp_path / "outside"
            outside.mkdir()
            survivor = outside / "external-taxpayer-evidence.bin"
            survivor.write_bytes(b"must survive")
            link_kind = _bind_directory(redirected_target, outside)

            ordinary_target = storage_path(ordinary_category)
            ordinary_target.mkdir(parents=True, exist_ok=True)
            ordinary = ordinary_target / "ordinary-cache.bin"
            ordinary.write_bytes(b"reclaimable only after complete preflight")

            with pytest.raises(StorageReclaimRefusedError) as caught:
                reclaim_storage_area(StorageArea.CACHE, confirmed=True)

        assert caught.value.area is StorageArea.CACHE
        assert caught.value.reason == "a selected target is not root-scoped"
        assert survivor.read_bytes() == b"must survive", f"external target lost through {link_kind}"
        assert ordinary.read_bytes() == b"reclaimable only after complete preflight"

    def test_reclaim_deletes_undeclared_nesting_beneath_a_selected_target(self, tmp_path) -> None:
        category = _targets(StorageArea.LOGS)[0]
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(category)
            nested = target / "undeclared" / "deep" / "entry.log"
            nested.parent.mkdir(parents=True, exist_ok=True)
            nested.write_bytes(b"regenerable")

            reclaim_storage_area(StorageArea.LOGS, confirmed=True)

        assert not nested.exists()
