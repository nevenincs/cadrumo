"""Behavioural gates on the inventory, tree check, and materialisation verbs.

Every expectation is derived from the taxonomy declaration rather than restated
as a literal path, so a member renamed at its declaration moves these tests with
it instead of leaving them asserting a name nothing writes.
"""

from __future__ import annotations

import os
import stat

import pytest

from ....core import (
    STORAGE_TAXONOMY,
    StorageArea,
    StorageCategory,
    StorageNodeKind,
    StorageScope,
    storage_path,
)
from ....core.storage_materialization import STORAGE_ROOT_MODE, ensure_storage_tree
from ....core.config import load_settings, override_settings
from ....core.directory_scan import (
    scan_directory,
)
from .._models import StorageAreaDisposition, StorageOccupancy, StorageTreeIssueKind
from .._service import (
    collect_storage_area_inventory,
    collect_storage_inventory,
    inspect_storage_tree,
    materialise_storage_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestInventoryCoversTheDeclaration:
    def test_public_inventory_has_exactly_one_row_per_area(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            report = collect_storage_area_inventory()

        assert tuple(row.area for row in report.rows) == tuple(StorageArea)
        assert {row.disposition for row in report.rows} == {
            StorageAreaDisposition.DURABLE,
            StorageAreaDisposition.RECLAIMABLE,
            StorageAreaDisposition.MIXED,
        }

    def test_public_inventory_measures_aggregate_bytes_without_internal_names(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LOGS)
            target.mkdir(parents=True, exist_ok=True)
            (target / "one.log").write_bytes(b"12345")
            report = collect_storage_area_inventory()

        logs = next(row for row in report.rows if row.area is StorageArea.LOGS)
        assert logs.occupancy is StorageOccupancy.POPULATED
        assert logs.footprint_bytes == 5
        assert logs.reclaimable

    def test_every_declared_member_gets_exactly_one_row(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            report = collect_storage_inventory()

        categories = [row.category for row in report.rows]
        assert len(categories) == len(set(categories))
        assert set(categories) == set(STORAGE_TAXONOMY)

    def test_root_scoped_rows_resolve_under_the_active_root(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            report = collect_storage_inventory()
            for row in report.rows:
                if row.scope is not StorageScope.ROOT:
                    continue
                assert row.path == storage_path(row.category)

    def test_row_axes_are_carried_from_the_declaration_verbatim(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            report = collect_storage_inventory()

        for row in report.rows:
            location = STORAGE_TAXONOMY[row.category]
            assert row.subpath == location.subpath
            assert row.node_kind is location.node_kind
            assert row.scope is location.scope
            assert row.grouping is location.grouping
            assert row.lifecycle is location.lifecycle
            assert row.override_policy is location.override_policy
            assert row.fingerprint_participation is location.fingerprint_participation
            assert row.settings_field == location.settings_field

    def test_a_scoped_member_reports_unresolved_rather_than_absent_with_no_profile(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            report = collect_storage_inventory()

        assert report.active_bucket_id is None
        scoped = [row for row in report.rows if row.scope is not StorageScope.ROOT]
        assert scoped
        for row in scoped:
            assert row.occupancy is StorageOccupancy.UNRESOLVED
            assert row.path is None


class TestOccupancyIsMeasuredNotAssumed:
    def test_an_absent_directory_reads_absent(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            assert not storage_path(StorageCategory.LOGS).exists()
            row = _row_for(collect_storage_inventory(), StorageCategory.LOGS)

        assert row.occupancy is StorageOccupancy.ABSENT
        assert row.entry_count == 0

    def test_a_materialised_but_unwritten_directory_reads_empty(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            storage_path(StorageCategory.LOGS).mkdir(parents=True, exist_ok=True)
            row = _row_for(collect_storage_inventory(), StorageCategory.LOGS)

        assert row.occupancy is StorageOccupancy.EMPTY
        assert row.entry_count == 0

    def test_a_written_directory_reads_populated_with_its_entry_count(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LOGS)
            target.mkdir(parents=True, exist_ok=True)
            (target / "one.log").write_bytes(b"a")
            (target / "two.log").write_bytes(b"b")
            row = _row_for(collect_storage_inventory(), StorageCategory.LOGS)

        assert row.occupancy is StorageOccupancy.POPULATED
        assert row.entry_count == 2

    def test_a_file_valued_member_reads_populated_only_when_it_carries_bytes(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.USAGE_RATIOS)
            assert STORAGE_TAXONOMY[StorageCategory.USAGE_RATIOS].node_kind is StorageNodeKind.FILE
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")
            empty = _row_for(collect_storage_inventory(), StorageCategory.USAGE_RATIOS)
            target.write_bytes(b"{}")
            written = _row_for(collect_storage_inventory(), StorageCategory.USAGE_RATIOS)

        assert empty.occupancy is StorageOccupancy.EMPTY
        assert written.occupancy is StorageOccupancy.POPULATED


class TestTreeCheckReportsWithoutRepairing:
    def test_an_unmaterialised_tree_reports_the_root_and_stays_unrepaired(self, tmp_path) -> None:
        absent_root = tmp_path / "never-created"
        with override_settings(cadrumo_local_storage_root=absent_root):
            report = inspect_storage_tree()

        assert not report.healthy
        assert any(issue.kind is StorageTreeIssueKind.MISSING_DIRECTORY for issue in report.issues)
        assert not absent_root.exists(), "check must never materialise what it reports missing"

    def test_a_materialised_tree_is_healthy(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            ensure_storage_tree(load_settings())
            report = inspect_storage_tree()

        assert report.checked_locations > 0
        assert report.healthy, [issue.model_dump(mode="json") for issue in report.issues]

    def test_a_file_where_a_directory_belongs_is_named_with_its_category(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            ensure_storage_tree(load_settings())
            target = storage_path(StorageCategory.LOGS)
            for entry in scan_directory(target):  # pragma: no cover - freshly materialised
                entry.unlink()
            target.rmdir()
            target.write_bytes(b"not a directory")
            report = inspect_storage_tree()

        offenders = [
            issue for issue in report.issues if issue.kind is StorageTreeIssueKind.FILE_WHERE_DIRECTORY_EXPECTED
        ]
        assert [issue.area for issue in offenders] == [StorageArea.LOGS]
        assert not report.healthy

    def test_a_directory_where_a_file_belongs_is_reported(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            ensure_storage_tree(load_settings())
            target = storage_path(StorageCategory.USAGE_RATIOS)
            target.mkdir(parents=True, exist_ok=True)
            report = inspect_storage_tree()

        offenders = [
            issue for issue in report.issues if issue.kind is StorageTreeIssueKind.DIRECTORY_WHERE_FILE_EXPECTED
        ]
        assert [issue.area for issue in offenders] == [StorageArea.EXPORTS]

    def test_a_file_valued_leaf_that_was_never_written_is_not_a_finding(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            ensure_storage_tree(load_settings())
            assert not storage_path(StorageCategory.USAGE_RATIOS).exists()
            report = inspect_storage_tree()

        assert report.healthy

    def test_root_permission_drift_is_reported_exactly_where_modes_are_enforced(self, tmp_path) -> None:
        """Both branches of the permission axis, asserted on whichever host runs this.

        Guarded inline rather than skipped, matching the materialiser's own
        mode-bit test: a skipped test reports nothing on the host that skipped
        it, so the branch that host DOES take goes unasserted. Everything above
        the guard runs everywhere, and each branch asserts the claim that is
        true there — drift is a finding where modes mean something, and the
        report says so rather than showing a clean permission axis where they
        do not.

        The POSIX branch carries its own positive control. A platform that
        accepts ``chmod`` and quietly ignores it would leave the mode unchanged,
        and the drift assertion would then be proving nothing; asserting the
        bits actually moved is what makes the finding evidence.
        """
        with override_settings(cadrumo_local_storage_root=tmp_path):
            ensure_storage_tree(load_settings())
            baseline = inspect_storage_tree()
            assert baseline.healthy, [issue.model_dump(mode="json") for issue in baseline.issues]
            assert baseline.root_mode_enforced is (os.name != "nt")

            tmp_path.chmod(0o755)
            drifted = inspect_storage_tree()

        found = [issue for issue in drifted.issues if issue.kind is StorageTreeIssueKind.ROOT_PERMISSIONS_DRIFTED]
        if os.name != "nt":
            assert stat.S_IMODE(tmp_path.stat().st_mode) != STORAGE_ROOT_MODE, (
                "the platform accepted a mode change without applying it, so the drift assertion below "
                "would pass against a check that never looked"
            )
            assert found
            assert not drifted.healthy
        else:
            assert not drifted.root_mode_enforced
            assert not found


class TestMaterialisePreservesContent:
    def test_init_creates_the_declared_tree_and_reports_what_it_made(self, tmp_path) -> None:
        root = tmp_path / "fresh"
        with override_settings(cadrumo_local_storage_root=root):
            report = materialise_storage_tree()
            verdict = inspect_storage_tree()

        assert report.storage_root == root
        assert report.created
        assert verdict.healthy

    def test_init_is_idempotent_and_never_removes_existing_content(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            materialise_storage_tree()
            marker = storage_path(StorageCategory.LOGS) / "survivor.log"
            marker.write_bytes(b"survivor")

            second = materialise_storage_tree()

            assert second.created == ()
            assert marker.read_bytes() == b"survivor"


def _row_for(report, category: StorageCategory):
    """Return the single inventory row for ``category``."""
    matches = [row for row in report.rows if row.category is category]
    assert len(matches) == 1
    return matches[0]
