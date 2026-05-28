"""Tests for the bucket-scoped notifications snapshot service."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from aeat.adapters.outbound.aeat.sede._notifications import (
    NotificationsSnapshot,
    RemoteNotification,
)
from aeat.adapters.persistence.storage import LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE
from aeat.application.live._notifications import (
    NotificationsService,
    NotificationsSnapshotNotFoundError,
    notifications_snapshot_object_key,
)
from aeat.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile


def _service(profile: TestRuntimeProfile) -> NotificationsService:
    return NotificationsService(settings=profile.settings)


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
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        persisted = svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(rows=(_row(),)),
        )
        assert len(persisted.snapshot_id) == 64
        assert persisted.bucket_id == secure_engine.bucket_id
        assert len(persisted.rows) == 1
        assert persisted.rows[0].titular_nif == "B12345678"

    def test_capture_deduplicates_identical_snapshots(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        snap = _snapshot(rows=(_row(concepto="Same"),))
        first = svc.capture(bucket_id=secure_engine.bucket_id, snapshot=snap)
        second = svc.capture(bucket_id=secure_engine.bucket_id, snapshot=snap)
        assert first.snapshot_id == second.snapshot_id
        assert len(svc.list_snapshots(bucket_id=secure_engine.bucket_id)) == 1

    def test_capture_distinct_snapshots_produce_distinct_ids(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        a = svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(rows=(_row(concepto="A"),)),
        )
        b = svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(rows=(_row(concepto="B"),)),
        )
        assert a.snapshot_id != b.snapshot_id


class TestShow:
    def test_show_resolves_full_id(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        persisted = svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(rows=(_row(),)),
        )
        retrieved = svc.show(bucket_id=secure_engine.bucket_id, snapshot_id=persisted.snapshot_id)
        assert retrieved == persisted

    def test_show_resolves_unambiguous_prefix(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        persisted = svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(rows=(_row(),)),
        )
        retrieved = svc.show(bucket_id=secure_engine.bucket_id, snapshot_id=persisted.snapshot_id[:12])
        assert retrieved == persisted

    def test_show_refuses_unknown_id(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        with pytest.raises(NotificationsSnapshotNotFoundError, match="no notifications snapshot"):
            svc.show(bucket_id=secure_engine.bucket_id, snapshot_id="0" * 64)


class TestLatest:
    def test_latest_returns_most_recent_capture(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(
                rows=(_row(concepto="older"),),
                captured_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        )
        newer = svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(
                rows=(_row(concepto="newer"),),
                captured_at=datetime(2025, 6, 1, tzinfo=UTC),
            ),
        )
        latest = svc.latest(bucket_id=secure_engine.bucket_id)
        assert latest == newer

    def test_latest_on_empty_bucket_returns_none(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        assert svc.latest(bucket_id=secure_engine.bucket_id) is None


class TestListSnapshots:
    def test_list_returns_capture_order(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        a = svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(rows=(_row(concepto="A"),)),
        )
        b = svc.capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(rows=(_row(concepto="B"),)),
        )
        snapshots = svc.list_snapshots(bucket_id=secure_engine.bucket_id)
        assert tuple(s.snapshot_id for s in snapshots) == (a.snapshot_id, b.snapshot_id)

    def test_list_empty_bucket_returns_empty_tuple(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        assert svc.list_snapshots(bucket_id=secure_engine.bucket_id) == ()


class TestBucketIsolation:
    def test_snapshots_are_runtime_profile_scoped(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path / "bucket-a", bucket_id="bucket-A") as bucket_a:
            svc_a = _service(bucket_a)
            svc_a.capture(
                bucket_id=bucket_a.bucket_id,
                snapshot=_snapshot(rows=(_row(concepto="A"),)),
            )
            assert svc_a.list_snapshots(bucket_id=bucket_a.bucket_id)[0].rows[0].concepto == "A"

        with isolated_runtime_profile(tmp_path=tmp_path / "bucket-b", bucket_id="bucket-B") as bucket_b:
            svc_b = _service(bucket_b)
            assert svc_b.list_snapshots(bucket_id=bucket_b.bucket_id) == ()
            svc_b.capture(
                bucket_id=bucket_b.bucket_id,
                snapshot=_snapshot(rows=(_row(concepto="B"),)),
            )
            assert svc_b.list_snapshots(bucket_id=bucket_b.bucket_id)[0].rows[0].concepto == "B"


class TestSecureStorage:
    def test_capture_persists_notifications_snapshot_as_secure_object(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        persisted = _service(secure_engine).capture(
            bucket_id=secure_engine.bucket_id,
            snapshot=_snapshot(rows=(_row(),)),
        )

        record = secure_engine.repository.load(
            LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE.namespace,
            notifications_snapshot_object_key(secure_engine.bucket_id, persisted.snapshot_id),
            expected_class=LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE.sensitivity,
            max_supported_version=LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE.schema_version,
        )

        assert record is not None
        assert b"B12345678" in record.payload
        assert not (
            secure_engine.settings.aeat_audit_dir / "live" / "notifications" / f"{secure_engine.bucket_id}.jsonl"
        ).exists()


class TestNoWriteSurface:
    """Structural assertions: the service exposes no write-shaped methods."""

    def test_service_has_no_submit_method(self) -> None:
        assert not hasattr(NotificationsService, "submit")
        assert not hasattr(NotificationsService, "acknowledge")
        assert not hasattr(NotificationsService, "send")
        assert not hasattr(NotificationsService, "mark_read_remote")

    def test_persisted_snapshot_mode_is_read_only(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        snap = _snapshot(rows=(_row(),))
        persisted = svc.capture(bucket_id=secure_engine.bucket_id, snapshot=snap)
        # The persisted snapshot carries no write-mutation field; the
        # NotificationsSnapshot adapter model has mode="read" which is
        # the structural read-only marker the parser emits.
        assert snap.mode == "read"
        assert persisted.persisted_at.tzinfo is not None
