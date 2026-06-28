"""Tests for the ``isolated_two_bucket_runtime`` multi-bucket fixture.

Authority: multi-bucket test fixture contract. Verifies
the fixture's contract: both buckets exist on disk with distinct
manifests; primary is the active profile by default;
``switch_to_secondary`` swaps the active pointer for its block;
each bucket's repository is independently reachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..adapters.persistence.storage.bucket._layout import bucket_paths
from ..adapters.persistence.storage.bucket._manifest_io import manifest_path, read_manifest
from ..core import resolve_active_bucket_id
from .secure_sql import isolated_two_bucket_runtime

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_PRIMARY = "fixture-test-primary"
_SECONDARY = "fixture-test-secondary"


def test_both_bucket_directories_exist_on_disk(tmp_path: Path) -> None:
    """Each bucket has its own directory + manifest under the shared storage root."""
    with isolated_two_bucket_runtime(
        tmp_path=tmp_path,
        primary_bucket_id=_PRIMARY,
        secondary_bucket_id=_SECONDARY,
    ) as runtime:
        primary_dir = bucket_paths(runtime.primary.storage_root, _PRIMARY).bucket_dir
        secondary_dir = bucket_paths(runtime.secondary.storage_root, _SECONDARY).bucket_dir
        assert primary_dir.is_dir()
        assert secondary_dir.is_dir()
        assert manifest_path(bucket_paths(runtime.primary.storage_root, _PRIMARY)).is_file()
        assert manifest_path(bucket_paths(runtime.secondary.storage_root, _SECONDARY)).is_file()


def test_primary_is_the_active_profile_by_default(tmp_path: Path) -> None:
    """``aeat_active_profile`` resolves to the primary on yield."""
    with isolated_two_bucket_runtime(
        tmp_path=tmp_path,
        primary_bucket_id=_PRIMARY,
        secondary_bucket_id=_SECONDARY,
    ):
        assert resolve_active_bucket_id() == _PRIMARY


def test_switch_to_secondary_swaps_active_profile_for_block(tmp_path: Path) -> None:
    """Inside the switch block the secondary is active; outside, primary is restored."""
    with isolated_two_bucket_runtime(
        tmp_path=tmp_path,
        primary_bucket_id=_PRIMARY,
        secondary_bucket_id=_SECONDARY,
    ) as runtime:
        assert resolve_active_bucket_id() == _PRIMARY
        with runtime.switch_to_secondary():
            assert resolve_active_bucket_id() == _SECONDARY
        assert resolve_active_bucket_id() == _PRIMARY


def test_each_bucket_has_distinct_manifest_label(tmp_path: Path) -> None:
    """Manifests carry the labels the fixture parameters supplied."""
    with isolated_two_bucket_runtime(
        tmp_path=tmp_path,
        primary_bucket_id=_PRIMARY,
        secondary_bucket_id=_SECONDARY,
        primary_label="Primary Label",
        secondary_label="Secondary Label",
    ) as runtime:
        primary_manifest = read_manifest(bucket_paths(runtime.primary.storage_root, _PRIMARY))
        secondary_manifest = read_manifest(bucket_paths(runtime.secondary.storage_root, _SECONDARY))
        assert primary_manifest.label == "Primary Label"
        assert secondary_manifest.label == "Secondary Label"


def test_each_bucket_repository_is_independently_addressable(tmp_path: Path) -> None:
    """Both repository handles point at distinct underlying bucket dirs."""
    with isolated_two_bucket_runtime(
        tmp_path=tmp_path,
        primary_bucket_id=_PRIMARY,
        secondary_bucket_id=_SECONDARY,
    ) as runtime:
        # The repository handles are real, distinct, and bound to
        # their own buckets — even though they share the storage
        # root, each carries its own session-bound engine.
        assert runtime.primary.repository is not runtime.secondary.repository
        assert runtime.primary.bucket_id != runtime.secondary.bucket_id
