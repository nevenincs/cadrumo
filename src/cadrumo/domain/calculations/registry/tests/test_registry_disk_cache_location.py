"""Registry disk-cache directory resolution after the cache-root relocation.

The cross-process registry pickle formerly always defaulted into the shared OS
temp directory. Production now derives ``<cadrumo_local_storage_root>/cache/registry``;
the pytest cross-worker share keeps the host temp directory (xdist workers each
get a per-pid storage root, so deriving from it would defeat the single-compile
sharing); an explicit override always wins. These tests exercise the pure
resolver with real inputs and the live accessor under pytest.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

import pytest

from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from ..loader_cache import (
    _resolve_registry_disk_cache_dir,
    registry_disk_cache_dir,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"registry", "cache"})
"""Taxonomy-vocabulary literals this module deliberately pins.

The ``"registry"`` in ``tmp_path / "state" / "cache" / "registry"`` is the
independent oracle pinned against ``StorageCategory.REGISTRY_DISK_CACHE``'s
declared subpath -- see the comment at the assertion. Not the CALCULATION
registry's bundled TOML tree several sibling test modules also spell
``"registry"``; this is the storage-taxonomy disk-cache location.
"""


def test_production_derives_cache_registry_under_storage_root(tmp_path: Path) -> None:
    resolved = _resolve_registry_disk_cache_dir(
        override=None,
        under_pytest=False,
        storage_root=tmp_path / "state",
    )
    # Pinned against the taxonomy's declared subpath rather than a restated
    # literal, so a re-declaration of the member is the only way to move this
    # assertion -- asserting the accessor equals itself would delete the
    # test's reason for existing.
    location = storage_location(StorageCategory.REGISTRY_DISK_CACHE)
    assert resolved == tmp_path / "state" / location.relative_path()
    assert resolved == tmp_path / "state" / "cache" / "registry"


def test_pytest_without_override_uses_host_shared_temp(tmp_path: Path) -> None:
    resolved = _resolve_registry_disk_cache_dir(
        override=None,
        under_pytest=True,
        storage_root=tmp_path / "state",
    )
    assert resolved == Path(tempfile.gettempdir())


def test_pytest_branch_is_a_declared_test_pinned_exception() -> None:
    """The pytest branch's divergence from the declared subpath is a positive
    declaration on the member, not an undeclared special case -- and every
    other member stays silent on the axis."""
    location = storage_location(StorageCategory.REGISTRY_DISK_CACHE)
    assert location.test_pinned_exception is not None
    assert location.test_pinned_exception.strip()
    other_members_with_exceptions = [
        category.value
        for category in StorageCategory
        if category is not StorageCategory.REGISTRY_DISK_CACHE
        and storage_location(category).test_pinned_exception is not None
    ]
    assert other_members_with_exceptions == []


def test_explicit_override_wins_in_either_environment(tmp_path: Path) -> None:
    override = tmp_path / "operator-cache"
    for under_pytest in (True, False):
        resolved = _resolve_registry_disk_cache_dir(
            override=override,
            under_pytest=under_pytest,
            storage_root=tmp_path / "state",
        )
        assert resolved == override


def test_live_accessor_under_pytest_returns_host_temp() -> None:
    # With no override, the live accessor resolves the host-shared temp
    # directory under pytest, keeping the bundled-root pickle shared across
    # xdist workers. Clear any ambient override so the assertion is
    # deterministic regardless of a sibling test's environment.
    from .....core.config import override_settings

    with override_settings(cadrumo_registry_disk_cache_dir=None):
        assert registry_disk_cache_dir() == Path(tempfile.gettempdir())
