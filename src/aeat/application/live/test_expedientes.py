"""Tests for the bucket-scoped expedientes snapshot service."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.outbound.aeat.sede._declarations import Declaracion
from aeat.adapters.persistence.storage import LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE
from aeat.application.live._expedientes import (
    ExpedientesCapture,
    ExpedientesService,
    ExpedientesSnapshotNotFoundError,
    expedientes_snapshot_object_key,
)
from aeat.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile


def _service(profile: TestRuntimeProfile) -> ExpedientesService:
    return ExpedientesService(settings=profile.settings)


def _declaration(
    *,
    modelo: str = "303",
    ejercicio: int = 2025,
    period: str = "1T",
    expediente_id: str = "12345678901234567890",
    estado: str = "ALTA",
    presented_at: datetime | None = None,
) -> Declaracion:
    return Declaracion(
        modelo=modelo,
        ejercicio=ejercicio,
        period=period,
        expediente_id=expediente_id,
        estado=estado,
        presented_at=presented_at or datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
    )


def _capture(
    *,
    declarations: tuple[Declaracion, ...] = (),
    captured_at: datetime | None = None,
) -> ExpedientesCapture:
    return ExpedientesCapture(
        declarations=declarations,
        captured_at=captured_at or datetime(2025, 4, 15, 10, 0, tzinfo=UTC),
        source_url="https://www6.agenciatributaria.gob.es/wlpl/CCD-WLPL/ConsultarDecl",
    )


class TestCapture:
    def test_capture_persists_with_content_addressed_id(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        persisted = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(),)),
        )
        assert len(persisted.snapshot_id) == 64
        assert persisted.bucket_id == secure_engine.bucket_id
        assert persisted.declarations[0].expediente_id == "12345678901234567890"

    def test_capture_deduplicates_identical_captures(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        cap = _capture(declarations=(_declaration(),))
        a = svc.capture(bucket_id=secure_engine.bucket_id, capture=cap)
        b = svc.capture(bucket_id=secure_engine.bucket_id, capture=cap)
        assert a.snapshot_id == b.snapshot_id
        assert len(svc.list_snapshots(bucket_id=secure_engine.bucket_id)) == 1

    def test_capture_distinct_inputs_yield_distinct_ids(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        a = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(modelo="303"),)),
        )
        b = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(modelo="130"),)),
        )
        assert a.snapshot_id != b.snapshot_id


class TestShow:
    def test_show_resolves_full_and_prefix(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        persisted = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(),)),
        )
        assert svc.show(bucket_id=secure_engine.bucket_id, snapshot_id=persisted.snapshot_id) == persisted
        assert svc.show(bucket_id=secure_engine.bucket_id, snapshot_id=persisted.snapshot_id[:10]) == persisted

    def test_show_refuses_unknown_id(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        with pytest.raises(ExpedientesSnapshotNotFoundError, match="no expedientes snapshot"):
            svc.show(bucket_id=secure_engine.bucket_id, snapshot_id="0" * 64)


class TestLatest:
    def test_latest_returns_newest_capture(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(
                declarations=(_declaration(),),
                captured_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        )
        newer = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(
                declarations=(_declaration(modelo="130"),),
                captured_at=datetime(2025, 6, 1, tzinfo=UTC),
            ),
        )
        assert svc.latest(bucket_id=secure_engine.bucket_id) == newer

    def test_latest_on_empty_bucket_is_none(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        assert svc.latest(bucket_id=secure_engine.bucket_id) is None


class TestBucketIsolation:
    def test_snapshots_are_runtime_profile_scoped(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path / "bucket-a", bucket_id="bucket-A") as bucket_a:
            svc_a = _service(bucket_a)
            svc_a.capture(
                bucket_id=bucket_a.bucket_id,
                capture=_capture(declarations=(_declaration(modelo="303"),)),
            )
            assert svc_a.list_snapshots(bucket_id=bucket_a.bucket_id)[0].declarations[0].modelo == "303"

        with isolated_runtime_profile(tmp_path=tmp_path / "bucket-b", bucket_id="bucket-B") as bucket_b:
            svc_b = _service(bucket_b)
            assert svc_b.list_snapshots(bucket_id=bucket_b.bucket_id) == ()
            svc_b.capture(
                bucket_id=bucket_b.bucket_id,
                capture=_capture(declarations=(_declaration(modelo="130"),)),
            )
            assert svc_b.list_snapshots(bucket_id=bucket_b.bucket_id)[0].declarations[0].modelo == "130"


class TestSecureStorage:
    def test_capture_persists_expedientes_snapshot_as_secure_object(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        persisted = _service(secure_engine).capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(),)),
        )

        record = secure_engine.repository.load(
            LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE.namespace,
            expedientes_snapshot_object_key(secure_engine.bucket_id, persisted.snapshot_id),
            expected_class=LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE.sensitivity,
            max_supported_version=LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE.schema_version,
        )

        assert record is not None
        assert b"12345678901234567890" in record.payload
        assert not (
            secure_engine.settings.aeat_audit_dir / "live" / "expedientes" / f"{secure_engine.bucket_id}.jsonl"
        ).exists()


class TestNoWriteSurface:
    def test_service_has_no_write_methods(self) -> None:
        assert not hasattr(ExpedientesService, "submit")
        assert not hasattr(ExpedientesService, "send")
        assert not hasattr(ExpedientesService, "modify")
        assert not hasattr(ExpedientesService, "delete_remote")

    def test_capture_mode_is_read_only_marker(self) -> None:
        cap = _capture(declarations=(_declaration(),))
        assert cap.mode == "read"
        # The Declaracion adapter model also carries mode='read'.
        assert cap.declarations[0].mode == "read"
