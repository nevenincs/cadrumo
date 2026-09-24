"""Outbound calc-sheets export orchestration and persistence integration.

The success path calls the real outbound Google adapter, which this project
never exercises in tests (write-shaped online tests are forbidden, matching
the sibling Google adapter suites). What IS exercised here, for real, is the
failure path: a run that never reaches Sheets still gets a sync-run record,
persisted through the genuine encrypted store — never a mock — proving the
failure-path co-write actually happens rather than being a design-only shell
around an untested call.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from .....application.storage.calc_sheets.engine import build_export_plan
from .....application.storage.calc_sheets.export_service import export_modelo_to_sheets
from .....core.sync_surface import SyncSurface
from .....domain.buckets.event import BucketEventType
from .....domain.calculations.registry.tests.published_authority import published_snapshot
from .....tests.google_credentials import unused_google_credentials
from ....persistence.profile.buckets import BucketEventHistoryRepository
from ....persistence.profile.sync_runs import SyncRunRecordRepository
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageValidationError
from ..calc_sheets_apply import apply_export_plan

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _m130_plan():
    snapshot = published_snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


def test_a_failed_apply_still_persists_a_sync_run_record_and_reraises(tmp_path: Path) -> None:
    """A blank root fails inside the outbound adapter before any network call.

    That makes this a real, deterministic, offline-triggerable failure: the
    blank-root validation is the adapter's own first line, so the exception
    this test drives is the SAME exception class a live refusal would raise,
    not a substitute for one.
    """
    plan = _m130_plan()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f5d2c9d7-2ca0-4036-80c1-a9880b662b18") as profile:
        repository = SyncRunRecordRepository()

        with pytest.raises(OutboundStorageValidationError):
            export_modelo_to_sheets(
                plan,
                credentials=unused_google_credentials(),
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
