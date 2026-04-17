"""Unit tests for :class:`aeat.status.StatusCache`."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from . import AeatStatusKind, Expediente, StatusCache

pytestmark = pytest.mark.unit

_URL = "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente?COPT=Y"


def _record(idx: int) -> Expediente:
    return Expediente.model_validate(
        {
            "expediente_id": f"2025X1234567L{idx:04d}",
            "modelo": "130",
            "period": "2025-1T",
            "status": "Presentada",
            "presented_at": datetime(2025, 4, 15, 10, 22, 31, tzinfo=UTC),
            "csv": None,
            "justificante_url": None,
            "source_page_url": _URL,
            "fetched_at": datetime(2025, 4, 15, 10, 22, 31, tzinfo=UTC),
        },
    )


class TestStatusCache:
    def test_miss_when_empty(self, tmp_path: Path) -> None:
        cache = StatusCache(tmp_path, ttl_s=60)
        assert (
            cache.get_tuple(
                surface=AeatStatusKind.EXPEDIENTE,
                key="deadbeef",
                model=Expediente,
            )
            is None
        )

    def test_hit_after_put(self, tmp_path: Path) -> None:
        cache = StatusCache(tmp_path, ttl_s=60)
        records = (_record(1), _record(2))
        cache.put_tuple(surface=AeatStatusKind.EXPEDIENTE, key="k1", records=records)
        got = cache.get_tuple(surface=AeatStatusKind.EXPEDIENTE, key="k1", model=Expediente)
        assert got is not None
        assert len(got) == 2
        assert got[0].expediente_id == "2025X1234567L0001"

    def test_ttl_expiry(self, tmp_path: Path) -> None:
        cache = StatusCache(tmp_path, ttl_s=0)
        cache.put_tuple(
            surface=AeatStatusKind.EXPEDIENTE,
            key="k1",
            records=(_record(1),),
        )
        time.sleep(0.01)
        assert (
            cache.get_tuple(
                surface=AeatStatusKind.EXPEDIENTE,
                key="k1",
                model=Expediente,
            )
            is None
        )

    def test_schema_mismatch_degrades_to_miss(self, tmp_path: Path) -> None:
        cache = StatusCache(tmp_path, ttl_s=60)
        cache.put_tuple(
            surface=AeatStatusKind.EXPEDIENTE,
            key="k1",
            records=(_record(1),),
        )
        # Tamper the payload so it no longer validates.
        payload_path = tmp_path / AeatStatusKind.EXPEDIENTE.value / "k1.json"
        payload_path.write_text('[{"bogus": true}]', encoding="utf-8")
        assert (
            cache.get_tuple(
                surface=AeatStatusKind.EXPEDIENTE,
                key="k1",
                model=Expediente,
            )
            is None
        )

    def test_missing_meta_degrades_to_miss(self, tmp_path: Path) -> None:
        cache = StatusCache(tmp_path, ttl_s=60)
        cache.put_tuple(
            surface=AeatStatusKind.EXPEDIENTE,
            key="k1",
            records=(_record(1),),
        )
        meta_path = tmp_path / AeatStatusKind.EXPEDIENTE.value / "k1.meta.json"
        meta_path.unlink()
        assert (
            cache.get_tuple(
                surface=AeatStatusKind.EXPEDIENTE,
                key="k1",
                model=Expediente,
            )
            is None
        )
