"""Tests for the bucket-scoped notifications snapshot service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from aeat.adapters.outbound.aeat.sede._notifications import (
    NotificationsSnapshot,
    RemoteNotification,
)
from aeat.application.live._notifications import (
    NotificationsService,
    NotificationsSnapshotNotFoundError,
)
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    return Settings(aeat_audit_dir=tmp_path / "audit")


def _row(*, certificado_id: str = "2596230606502", concepto: str = "Sample") -> RemoteNotification:
    from datetime import date

    return RemoteNotification(
        certificado_id=certificado_id,
        tipo="notificacion",
        concepto=concepto,
        titular_nif="B12345678",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345678",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=None,
        modo_notificacion=None,
        leida=None,
        source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/GNNO-JDIT/SvInteresadosQuery"),
    )


def _snapshot(
    *,
    rows: tuple[RemoteNotification, ...] = (),
    captured_at: datetime | None = None,
    source_url: str = "https://www6.agenciatributaria.gob.es/wlpl/GNNO-JDIT/ResumenInteresados",
) -> NotificationsSnapshot:
    return NotificationsSnapshot(
        rows=rows,
        captured_at=captured_at or datetime(2025, 3, 15, 10, 0, tzinfo=UTC),
        source_url=AnyHttpUrl(source_url),
    )


class TestCapture:
    def test_capture_persists_snapshot_with_content_addressed_id(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = NotificationsService(settings=isolated_settings)
        persisted = svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(rows=(_row(),)),
        )
        assert len(persisted.snapshot_id) == 64
        assert persisted.bucket_id == "bucket-001"
        assert len(persisted.rows) == 1
        assert persisted.rows[0].titular_nif == "B12345678"

    def test_capture_deduplicates_identical_snapshots(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = NotificationsService(settings=isolated_settings)
        snap = _snapshot(rows=(_row(concepto="Same"),))
        first = svc.capture(bucket_id="bucket-001", snapshot=snap)
        second = svc.capture(bucket_id="bucket-001", snapshot=snap)
        assert first.snapshot_id == second.snapshot_id
        assert len(svc.list_snapshots(bucket_id="bucket-001")) == 1

    def test_capture_distinct_snapshots_produce_distinct_ids(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = NotificationsService(settings=isolated_settings)
        a = svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(rows=(_row(concepto="A"),)),
        )
        b = svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(rows=(_row(concepto="B"),)),
        )
        assert a.snapshot_id != b.snapshot_id


class TestShow:
    def test_show_resolves_full_id(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        persisted = svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(rows=(_row(),)),
        )
        retrieved = svc.show(bucket_id="bucket-001", snapshot_id=persisted.snapshot_id)
        assert retrieved == persisted

    def test_show_resolves_unambiguous_prefix(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        persisted = svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(rows=(_row(),)),
        )
        retrieved = svc.show(bucket_id="bucket-001", snapshot_id=persisted.snapshot_id[:12])
        assert retrieved == persisted

    def test_show_refuses_unknown_id(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        with pytest.raises(NotificationsSnapshotNotFoundError, match="no notifications snapshot"):
            svc.show(bucket_id="bucket-001", snapshot_id="0" * 64)


class TestLatest:
    def test_latest_returns_most_recent_capture(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(
                rows=(_row(concepto="older"),),
                captured_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        )
        newer = svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(
                rows=(_row(concepto="newer"),),
                captured_at=datetime(2025, 6, 1, tzinfo=UTC),
            ),
        )
        latest = svc.latest(bucket_id="bucket-001")
        assert latest == newer

    def test_latest_on_empty_bucket_returns_none(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        assert svc.latest(bucket_id="bucket-001") is None


class TestListSnapshots:
    def test_list_returns_capture_order(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        a = svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(rows=(_row(concepto="A"),)),
        )
        b = svc.capture(
            bucket_id="bucket-001",
            snapshot=_snapshot(rows=(_row(concepto="B"),)),
        )
        snapshots = svc.list_snapshots(bucket_id="bucket-001")
        assert tuple(s.snapshot_id for s in snapshots) == (a.snapshot_id, b.snapshot_id)

    def test_list_empty_bucket_returns_empty_tuple(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        assert svc.list_snapshots(bucket_id="bucket-001") == ()


class TestBucketIsolation:
    def test_snapshots_are_bucket_scoped(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        svc.capture(
            bucket_id="bucket-A",
            snapshot=_snapshot(rows=(_row(concepto="A"),)),
        )
        svc.capture(
            bucket_id="bucket-B",
            snapshot=_snapshot(rows=(_row(concepto="B"),)),
        )
        assert len(svc.list_snapshots(bucket_id="bucket-A")) == 1
        assert len(svc.list_snapshots(bucket_id="bucket-B")) == 1
        assert svc.list_snapshots(bucket_id="bucket-A")[0].rows[0].concepto == "A"
        assert svc.list_snapshots(bucket_id="bucket-B")[0].rows[0].concepto == "B"


class TestNoWriteSurface:
    """Structural assertions: the service exposes no write-shaped methods."""

    def test_service_has_no_submit_method(self) -> None:
        assert not hasattr(NotificationsService, "submit")
        assert not hasattr(NotificationsService, "acknowledge")
        assert not hasattr(NotificationsService, "send")
        assert not hasattr(NotificationsService, "mark_read_remote")

    def test_persisted_snapshot_mode_is_read_only(self, isolated_settings: Settings) -> None:
        svc = NotificationsService(settings=isolated_settings)
        snap = _snapshot(rows=(_row(),))
        persisted = svc.capture(bucket_id="bucket-001", snapshot=snap)
        # The persisted snapshot carries no write-mutation field; the
        # NotificationsSnapshot adapter model has mode="read" which is
        # the structural read-only marker the parser emits.
        assert snap.mode == "read"
        assert persisted.persisted_at.tzinfo is not None
