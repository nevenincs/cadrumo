"""``export_modelo_to_sheets`` records provenance on failure, before it can succeed.

The success path calls the real outbound Google adapter, which this project
never exercises in tests (write-shaped online tests are forbidden, matching
every sibling in ``adapters.outbound.google.tests``). What IS exercised here,
for real, is the half this row exists to add: a run that never reaches Sheets
still gets a sync-run record, persisted through the genuine encrypted store —
never a mock — proving the failure-path co-write actually happens rather than
being a design-only shell around an untested call.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from .....adapters.outbound.google import apply_export_plan
from .....adapters.outbound.storage import OutboundStorageValidationError
from .....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from .....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from .....core import SyncSurface
from .....core.resources import resources
from .....domain.buckets import BucketEventType
from .....tests.secure_sql import isolated_runtime_profile
from .._engine import build_export_plan
from .._export_service import _export_scope_description, _SingleExportCoverage, export_modelo_to_sheets

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m130_plan():
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


class TestSingleExportCoverage:
    """The coverage source's contract: one unit, no divergence concept."""

    def test_a_reached_export_counts_one_unit_and_no_divergences(self) -> None:
        coverage = _SingleExportCoverage(reached=True)
        assert coverage.reached_count == 1
        assert coverage.divergences == ()

    def test_an_unreached_export_counts_zero(self) -> None:
        coverage = _SingleExportCoverage(reached=False)
        assert coverage.reached_count == 0
        assert coverage.divergences == ()


def test_scope_description_names_modelo_period_and_year() -> None:
    plan = _m130_plan()
    scope = _export_scope_description(plan)
    assert plan.metadata.modelo_id in scope
    assert plan.metadata.period.registry_token in scope
    assert str(plan.metadata.filing_year) in scope


def test_a_failed_apply_still_persists_a_sync_run_record_and_reraises(tmp_path: Path) -> None:
    """``root_folder_id=""`` fails inside ``apply_export_plan`` before any network call.

    That is what makes this a real, deterministic, offline-triggerable failure:
    the blank-root validation is the adapter's own first line, so the
    exception this test drives is the SAME exception class a live refusal
    would raise, not a substitute for one.
    """
    plan = _m130_plan()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f5d2c9d7-2ca0-4036-80c1-a9880b662b18") as profile:
        repository = SyncRunRecordRepository()

        with pytest.raises(OutboundStorageValidationError):
            export_modelo_to_sheets(
                plan,
                credentials=object(),
                root_folder_id="",
                sync_run_repository=repository,
                apply_export_plan=apply_export_plan,
            )

        records = [repository.load(identifier) for identifier in repository.iter_ids()]
        assert len(records) == 1, "exactly one sync-run record must exist after the failed run"
        record = records[0]
        assert record is not None

        assert record.bucket_id == profile.bucket_id
        assert record.surface == SyncSurface.CALC_SHEETS_EXPORT
        assert record.succeeded is False
        assert record.unit_count == 0
        assert record.divergence_count == 0
        assert plan.metadata.modelo_id in record.resolved_scope

        events = BucketEventHistoryRepository().load().events
        assert record.bucket_event_id in events, "the co-written bucket event must exist alongside the record"
        assert events[record.bucket_event_id].event_type is BucketEventType.SYNC_RUN_CALC_SHEETS_EXPORT_COMPLETED
