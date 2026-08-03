"""Behavioural gate on the reclaim guard.

``reclaim`` is the one verb on this surface that deletes operator data, so its
refusal is tested as behaviour against real files on a real temporary root: a
refused category must still hold every byte it held before the call.

The suite is written to survive its own mutation proof. Deleting the lifecycle
check must red a test, and so must inverting it — a refusal suite with no
positive control passes against a guard that refuses everything, which is the
failure mode that looks safest and is the easiest to ship.
"""

from __future__ import annotations

import pytest

from ....core import (
    STORAGE_TAXONOMY,
    StorageCategory,
    StorageLifecycle,
    StorageNodeKind,
    StorageScope,
    storage_path,
)
from ....core.config import override_settings
from .._errors import StorageReclaimRefusedError, StorageReclaimUnconfirmedError
from .._service import (
    RECLAIMABLE_LIFECYCLES,
    collect_storage_inventory,
    reclaim_storage_category,
    storage_lifecycle_permits_reclaim,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_RECLAIMABLE_ROOT_CATEGORIES = tuple(
    category
    for category, location in STORAGE_TAXONOMY.items()
    if location.scope is StorageScope.ROOT
    and location.node_kind is StorageNodeKind.DIRECTORY
    and location.lifecycle in RECLAIMABLE_LIFECYCLES
)

_PROTECTED_ROOT_CATEGORIES = tuple(
    category
    for category, location in STORAGE_TAXONOMY.items()
    if location.scope is StorageScope.ROOT and location.lifecycle not in RECLAIMABLE_LIFECYCLES
)

_BUCKET_SCOPED_CATEGORIES = tuple(
    category for category, location in STORAGE_TAXONOMY.items() if location.scope is not StorageScope.ROOT
)


def _seed(path, *, name: str = "seeded.bin") -> None:
    """Write one real file and one nested file beneath ``path``."""
    path.mkdir(parents=True, exist_ok=True)
    (path / name).write_bytes(b"operator data")
    nested = path / "nested" / "deeper"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / name).write_bytes(b"nested operator data")


class TestPartitionIsNonVacuous:
    """The parametrised suites below are only worth anything if both sides exist."""

    def test_both_sides_of_the_lifecycle_partition_are_populated(self) -> None:
        assert _RECLAIMABLE_ROOT_CATEGORIES, "no reclaimable category, so the accept suite checks nothing"
        assert _PROTECTED_ROOT_CATEGORIES, "no protected category, so the refusal suite checks nothing"
        assert _BUCKET_SCOPED_CATEGORIES, "no scoped category, so the scope refusal checks nothing"

    def test_the_permitted_set_is_exactly_the_bounded_lifecycles(self) -> None:
        assert {
            StorageLifecycle.RETENTION,
            StorageLifecycle.ROTATION,
            StorageLifecycle.TTL,
        } == RECLAIMABLE_LIFECYCLES
        assert not storage_lifecycle_permits_reclaim(StorageLifecycle.UNBOUNDED_BY_DESIGN)


class TestGuardRefusesProtectedCategories:
    @pytest.mark.parametrize("category", _PROTECTED_ROOT_CATEGORIES, ids=lambda c: c.value)
    def test_a_protected_category_is_refused_with_its_content_intact(self, category, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(category)
            location = STORAGE_TAXONOMY[category]
            if location.node_kind is StorageNodeKind.FILE:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"operator data")
            else:
                _seed(target)

            with pytest.raises(StorageReclaimRefusedError) as caught:
                reclaim_storage_category(category, confirmed=True)

            assert caught.value.category is category
            assert caught.value.lifecycle is location.lifecycle
            if location.node_kind is StorageNodeKind.FILE:
                assert target.read_bytes() == b"operator data"
            else:
                assert (target / "seeded.bin").read_bytes() == b"operator data"
                assert (target / "nested" / "deeper" / "seeded.bin").exists()

    def test_the_refusal_names_the_path_the_lifecycle_and_the_entry_count(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.BLOBS)
            _seed(target)

            with pytest.raises(StorageReclaimRefusedError) as caught:
                reclaim_storage_category(StorageCategory.BLOBS, confirmed=True)

        error = caught.value
        assert error.path == target
        assert error.entry_count == 2
        assert StorageLifecycle.UNBOUNDED_BY_DESIGN.value in error.reason
        rendered = str(error)
        assert str(target) in rendered
        assert StorageCategory.BLOBS.value in rendered

    @pytest.mark.parametrize("category", _BUCKET_SCOPED_CATEGORIES, ids=lambda c: c.value)
    def test_a_scoped_member_is_refused_because_its_bucket_owns_the_ordering(self, category, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path), pytest.raises(StorageReclaimRefusedError):
            reclaim_storage_category(category, confirmed=True)


class TestGuardAcceptsReclaimableCategories:
    """The positive control: an all-refusing guard must not pass this file."""

    @pytest.mark.parametrize("category", _RECLAIMABLE_ROOT_CATEGORIES, ids=lambda c: c.value)
    def test_a_reclaimable_category_loses_its_contents_and_keeps_its_directory(self, category, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(category)
            _seed(target)

            report = reclaim_storage_category(category, confirmed=True)

            assert report.category is category
            assert report.path == target
            assert report.removed_entries == 2
            assert report.retained_entries == 0
            assert target.is_dir()
            assert not list(target.iterdir())

    def test_reclaim_removes_undeclared_nesting_beneath_the_category(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LOGS)
            undeclared = target / "not-in-the-taxonomy" / "one-level-deeper"
            undeclared.mkdir(parents=True, exist_ok=True)
            (undeclared / "artefact.log").write_bytes(b"x" * 32)

            report = reclaim_storage_category(StorageCategory.LOGS, confirmed=True)

            assert report.removed_entries == 1
            assert not undeclared.exists()
            assert target.is_dir()

    def test_reclaiming_an_absent_category_is_a_clean_no_op(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LLM_CACHE)
            assert not target.exists()

            report = reclaim_storage_category(StorageCategory.LLM_CACHE, confirmed=True)

            assert report.removed_entries == 0


class TestConfirmationIsRequiredAtTheServiceBoundary:
    def test_an_unconfirmed_reclaim_refuses_and_deletes_nothing(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LOGS)
            _seed(target)

            with pytest.raises(StorageReclaimUnconfirmedError) as caught:
                reclaim_storage_category(StorageCategory.LOGS)

            assert (target / "seeded.bin").exists()
            assert caught.value.entry_count == 2
            assert str(target) in str(caught.value)


class TestInventoryAgreesWithTheGuard:
    """A row that advertises reclaimability the guard would refuse is a lie."""

    def test_every_row_reclaimable_flag_matches_what_reclaim_accepts(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            report = collect_storage_inventory()
            for row in report.rows:
                if row.reclaimable:
                    continue
                with pytest.raises((StorageReclaimRefusedError, StorageReclaimUnconfirmedError)) as caught:
                    reclaim_storage_category(row.category, confirmed=True)
                assert isinstance(caught.value, StorageReclaimRefusedError), (
                    f"{row.category.value} is advertised as not reclaimable but the guard let it through"
                )
