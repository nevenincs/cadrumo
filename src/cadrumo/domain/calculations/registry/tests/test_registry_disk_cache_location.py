"""Registry disk-cache directory resolution after the cache-root relocation.

The cross-process registry pickle formerly always defaulted into the shared OS
temp directory. Production now derives ``<cadrumo_local_storage_root>/cache/registry``;
the pytest cross-worker share keeps the host temp directory (xdist workers each
get a per-pid storage root, so deriving from it would defeat the single-compile
sharing); an explicit override always wins. These tests exercise the pure
resolver with real inputs and the live accessor under pytest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from ..loader_cache import (
    _resolve_registry_disk_cache_dir,
    registry_disk_cache_dir,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_production_derives_cache_registry_under_storage_root(tmp_path: Path) -> None:
    resolved = _resolve_registry_disk_cache_dir(
        override=None,
        storage_root=tmp_path / "state",
    )
    # Pinned against the taxonomy's declared subpath rather than a restated
    # literal, so a re-declaration of the member is the only way to move this
    # assertion -- asserting the accessor equals itself would delete the
    # test's reason for existing.
    location = storage_location(StorageCategory.REGISTRY_DISK_CACHE)
    assert resolved == tmp_path / "state" / location.relative_path()
    assert resolved == tmp_path / "state" / "cache" / "registry"


def test_explicit_override_wins(tmp_path: Path) -> None:
    override = tmp_path / "operator-cache"
    resolved = _resolve_registry_disk_cache_dir(override=override, storage_root=tmp_path / "state")
    assert resolved == override


def test_live_accessor_uses_the_configured_storage_root(tmp_path: Path) -> None:
    from .....core.config import override_settings

    with override_settings(cadrumo_registry_disk_cache_dir=None, cadrumo_local_storage_root=tmp_path):
        assert registry_disk_cache_dir() == tmp_path / "cache" / "registry"
