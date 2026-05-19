"""Tests for the bucket-scoped expedientes snapshot service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.outbound.aeat.sede._declarations import Declaracion
from aeat.application.live._expedientes import (
    ExpedientesCapture,
    ExpedientesService,
    ExpedientesSnapshotNotFoundError,
)
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    return Settings(aeat_audit_dir=tmp_path / "audit")


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
        isolated_settings: Settings,
    ) -> None:
        svc = ExpedientesService(settings=isolated_settings)
        persisted = svc.capture(
            bucket_id="bucket-001",
            capture=_capture(declarations=(_declaration(),)),
        )
        assert len(persisted.snapshot_id) == 64
        assert persisted.bucket_id == "bucket-001"
        assert persisted.declarations[0].expediente_id == "12345678901234567890"

    def test_capture_deduplicates_identical_captures(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ExpedientesService(settings=isolated_settings)
        cap = _capture(declarations=(_declaration(),))
        a = svc.capture(bucket_id="bucket-001", capture=cap)
        b = svc.capture(bucket_id="bucket-001", capture=cap)
        assert a.snapshot_id == b.snapshot_id
        assert len(svc.list_snapshots(bucket_id="bucket-001")) == 1

    def test_capture_distinct_inputs_yield_distinct_ids(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ExpedientesService(settings=isolated_settings)
        a = svc.capture(
            bucket_id="bucket-001",
            capture=_capture(declarations=(_declaration(modelo="303"),)),
        )
        b = svc.capture(
            bucket_id="bucket-001",
            capture=_capture(declarations=(_declaration(modelo="130"),)),
        )
        assert a.snapshot_id != b.snapshot_id


class TestShow:
    def test_show_resolves_full_and_prefix(self, isolated_settings: Settings) -> None:
        svc = ExpedientesService(settings=isolated_settings)
        persisted = svc.capture(
            bucket_id="bucket-001",
            capture=_capture(declarations=(_declaration(),)),
        )
        assert svc.show(bucket_id="bucket-001", snapshot_id=persisted.snapshot_id) == persisted
        assert svc.show(bucket_id="bucket-001", snapshot_id=persisted.snapshot_id[:10]) == persisted

    def test_show_refuses_unknown_id(self, isolated_settings: Settings) -> None:
        svc = ExpedientesService(settings=isolated_settings)
        with pytest.raises(ExpedientesSnapshotNotFoundError, match="no expedientes snapshot"):
            svc.show(bucket_id="bucket-001", snapshot_id="0" * 64)


class TestLatest:
    def test_latest_returns_newest_capture(self, isolated_settings: Settings) -> None:
        svc = ExpedientesService(settings=isolated_settings)
        svc.capture(
            bucket_id="bucket-001",
            capture=_capture(
                declarations=(_declaration(),),
                captured_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        )
        newer = svc.capture(
            bucket_id="bucket-001",
            capture=_capture(
                declarations=(_declaration(modelo="130"),),
                captured_at=datetime(2025, 6, 1, tzinfo=UTC),
            ),
        )
        assert svc.latest(bucket_id="bucket-001") == newer

    def test_latest_on_empty_bucket_is_none(self, isolated_settings: Settings) -> None:
        svc = ExpedientesService(settings=isolated_settings)
        assert svc.latest(bucket_id="bucket-001") is None


class TestBucketIsolation:
    def test_snapshots_are_bucket_scoped(self, isolated_settings: Settings) -> None:
        svc = ExpedientesService(settings=isolated_settings)
        svc.capture(
            bucket_id="bucket-A",
            capture=_capture(declarations=(_declaration(modelo="303"),)),
        )
        svc.capture(
            bucket_id="bucket-B",
            capture=_capture(declarations=(_declaration(modelo="130"),)),
        )
        a = svc.list_snapshots(bucket_id="bucket-A")
        b = svc.list_snapshots(bucket_id="bucket-B")
        assert len(a) == 1
        assert len(b) == 1
        assert a[0].declarations[0].modelo == "303"
        assert b[0].declarations[0].modelo == "130"


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
