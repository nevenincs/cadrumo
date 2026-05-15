"""Tests for the bucket-scoped borrador 100 snapshot service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.application.live._borrador import (
    BorradorPrefillEntry,
    BorradorService,
    BorradorSnapshotNotFoundError,
)
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    return Settings(aeat_audit_dir=tmp_path / "audit")


def _entry(*, casilla: str = "100", value: str = "1000.00", label: str = "") -> BorradorPrefillEntry:
    return BorradorPrefillEntry(
        casilla_id=casilla,
        value=Decimal(value),
        source_label=label,
    )


_SOURCE = "https://www2.agenciatributaria.gob.es/wlpl/PRET-R210/SimuladorOpenAjax"


class TestCapture:
    def test_capture_persists_with_content_addressed_id(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = BorradorService(settings=isolated_settings)
        snap = svc.capture(
            bucket_id="bucket-001",
            tax_year=2024,
            captured_at=datetime(2025, 3, 15, 10, 0, tzinfo=UTC),
            source_url=_SOURCE,
            prefill_entries=(_entry(casilla="100", value="1000.00"),),
        )
        assert len(snap.snapshot_id) == 64
        assert snap.tax_year == 2024
        assert snap.bucket_id == "bucket-001"
        assert len(snap.prefill_entries) == 1
        assert snap.prefill_entries[0].value == Decimal("1000.00")

    def test_capture_deduplicates_identical_snapshots(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = BorradorService(settings=isolated_settings)
        captured_at = datetime(2025, 3, 15, tzinfo=UTC)
        prefill_entries = (_entry(),)
        a = svc.capture(
            bucket_id="bucket-001",
            tax_year=2024,
            captured_at=captured_at,
            source_url=_SOURCE,
            prefill_entries=prefill_entries,
        )
        b = svc.capture(
            bucket_id="bucket-001",
            tax_year=2024,
            captured_at=captured_at,
            source_url=_SOURCE,
            prefill_entries=prefill_entries,
        )
        assert a.snapshot_id == b.snapshot_id
        assert len(svc.list_snapshots(bucket_id="bucket-001")) == 1

    def test_capture_distinct_entries_yield_distinct_ids(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = BorradorService(settings=isolated_settings)
        bucket_id = "bucket-001"
        tax_year = 2024
        captured_at = datetime(2025, 3, 15, tzinfo=UTC)
        source_url = _SOURCE
        a = svc.capture(
            bucket_id=bucket_id,
            tax_year=tax_year,
            captured_at=captured_at,
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="1000"),),
        )
        b = svc.capture(
            bucket_id=bucket_id,
            tax_year=tax_year,
            captured_at=captured_at,
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="2000"),),
        )
        assert a.snapshot_id != b.snapshot_id

    def test_capture_id_is_entry_order_invariant(self, isolated_settings: Settings) -> None:
        svc = BorradorService(settings=isolated_settings)
        bucket_id = "bucket-001"
        tax_year = 2024
        captured_at = datetime(2025, 3, 15, tzinfo=UTC)
        source_url = _SOURCE
        entries_a = (_entry(casilla="100", value="1000"), _entry(casilla="200", value="2000"))
        entries_b = (_entry(casilla="200", value="2000"), _entry(casilla="100", value="1000"))
        a = svc.capture(
            bucket_id=bucket_id,
            tax_year=tax_year,
            captured_at=captured_at,
            source_url=source_url,
            prefill_entries=entries_a,
        )
        # Need a fresh storage to dedup-bypass: same snapshot_id by content
        svc.discard(bucket_id=bucket_id, snapshot_id=a.snapshot_id)
        b = svc.capture(
            bucket_id=bucket_id,
            tax_year=tax_year,
            captured_at=captured_at,
            source_url=source_url,
            prefill_entries=entries_b,
        )
        # Hash is computed from sorted entries, so a/b share id; second
        # capture deduplicates to the existing record. The dedup-hit
        # preserves discarded=True from the first capture.
        assert a.snapshot_id == b.snapshot_id


class TestShow:
    def test_show_resolves_full_and_prefix(self, isolated_settings: Settings) -> None:
        svc = BorradorService(settings=isolated_settings)
        snap = svc.capture(
            bucket_id="b1",
            tax_year=2024,
            captured_at=datetime(2025, 3, 15, tzinfo=UTC),
            source_url=_SOURCE,
            prefill_entries=(_entry(),),
        )
        assert svc.show(bucket_id="b1", snapshot_id=snap.snapshot_id) == snap
        assert svc.show(bucket_id="b1", snapshot_id=snap.snapshot_id[:8]) == snap

    def test_show_refuses_unknown_id(self, isolated_settings: Settings) -> None:
        svc = BorradorService(settings=isolated_settings)
        with pytest.raises(BorradorSnapshotNotFoundError, match="no borrador 100 snapshot"):
            svc.show(bucket_id="b1", snapshot_id="0" * 64)


class TestListAndLatest:
    def test_list_excludes_discarded_by_default(self, isolated_settings: Settings) -> None:
        svc = BorradorService(settings=isolated_settings)
        bucket_id = "b1"
        tax_year = 2024
        source_url = _SOURCE
        a = svc.capture(
            bucket_id=bucket_id,
            tax_year=tax_year,
            captured_at=datetime(2025, 1, 1, tzinfo=UTC),
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="100"),),
        )
        b = svc.capture(
            bucket_id=bucket_id,
            tax_year=tax_year,
            captured_at=datetime(2025, 6, 1, tzinfo=UTC),
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="200"),),
        )
        svc.discard(bucket_id=bucket_id, snapshot_id=a.snapshot_id, reason="stale")
        visible = svc.list_snapshots(bucket_id=bucket_id)
        with_discarded = svc.list_snapshots(bucket_id=bucket_id, include_discarded=True)
        assert len(visible) == 1
        assert visible[0].snapshot_id == b.snapshot_id
        assert len(with_discarded) == 2

    def test_latest_for_year_filters_year_and_excludes_discarded(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = BorradorService(settings=isolated_settings)
        bucket_id = "b1"
        source_url = _SOURCE
        svc.capture(
            bucket_id=bucket_id,
            tax_year=2023,
            captured_at=datetime(2024, 6, 1, tzinfo=UTC),
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="500"),),
        )
        newer = svc.capture(
            bucket_id=bucket_id,
            tax_year=2024,
            captured_at=datetime(2025, 6, 1, tzinfo=UTC),
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="1000"),),
        )
        older = svc.capture(
            bucket_id=bucket_id,
            tax_year=2024,
            captured_at=datetime(2025, 1, 1, tzinfo=UTC),
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="900"),),
        )
        latest = svc.latest_for_year(bucket_id=bucket_id, tax_year=2024)
        assert latest == newer
        # Discarding the newer one falls back to older.
        svc.discard(bucket_id=bucket_id, snapshot_id=newer.snapshot_id)
        latest_after_discard = svc.latest_for_year(bucket_id=bucket_id, tax_year=2024)
        assert latest_after_discard == older

    def test_latest_for_year_returns_none_when_empty(self, isolated_settings: Settings) -> None:
        svc = BorradorService(settings=isolated_settings)
        assert svc.latest_for_year(bucket_id="b1", tax_year=2024) is None


class TestDiscard:
    def test_discard_marks_snapshot_and_records_reason(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = BorradorService(settings=isolated_settings)
        snap = svc.capture(
            bucket_id="b1",
            tax_year=2024,
            captured_at=datetime(2025, 3, 15, tzinfo=UTC),
            source_url=_SOURCE,
            prefill_entries=(_entry(),),
        )
        updated = svc.discard(
            bucket_id="b1",
            snapshot_id=snap.snapshot_id,
            reason="profile changed",
        )
        assert updated.discarded is True
        assert updated.discarded_reason == "profile changed"
        assert updated.discarded_at is not None


class TestBucketIsolation:
    def test_snapshots_are_bucket_scoped(self, isolated_settings: Settings) -> None:
        svc = BorradorService(settings=isolated_settings)
        tax_year = 2024
        captured_at = datetime(2025, 3, 15, tzinfo=UTC)
        source_url = _SOURCE
        svc.capture(
            bucket_id="bucket-A",
            tax_year=tax_year,
            captured_at=captured_at,
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="100"),),
        )
        svc.capture(
            bucket_id="bucket-B",
            tax_year=tax_year,
            captured_at=captured_at,
            source_url=source_url,
            prefill_entries=(_entry(casilla="100", value="200"),),
        )
        a = svc.list_snapshots(bucket_id="bucket-A")
        b = svc.list_snapshots(bucket_id="bucket-B")
        assert len(a) == 1
        assert len(b) == 1
        assert a[0].prefill_entries[0].value == Decimal("100")
        assert b[0].prefill_entries[0].value == Decimal("200")


class TestNoWriteSurface:
    def test_service_has_no_remote_mutation_methods(self) -> None:
        assert not hasattr(BorradorService, "submit")
        assert not hasattr(BorradorService, "send")
        assert not hasattr(BorradorService, "push")
        assert not hasattr(BorradorService, "modify_remote")
        assert not hasattr(BorradorService, "filing_remote")
