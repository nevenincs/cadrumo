"""Tests for the governed-persistence :class:`ModeloHistoryRepository`.

Exercises round-trip save/load, list/iter, deletion, the AUDIT
classification gate, unsafe-modelo rejection, and the per-modelo lock
isolation guarantees.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage import Envelope, SensitivityClass
from ....adapters.persistence.storage.errors import ClassificationError
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import Period
from ....domain import ModeloIdentifier
from ....tests.secure_sql import TestRuntimeProfile
from .._history_models import ModeloHistory, ModeloHistoryEntry
from .._history_repository import ModeloHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FOREIGN_CLASS_WRITTEN_AT = datetime(2026, 5, 26, 17, 30, 0, tzinfo=UTC)


def _make_history(*, modelo: str = "130", n_entries: int = 2) -> ModeloHistory:
    base = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    entries = tuple(
        ModeloHistoryEntry(
            modelo=ModeloIdentifier(modelo),
            period=Period.from_year_and_code(2026, f"{i + 1}T"),
            submitted_at=base.replace(month=1 + 3 * i),
            status="ACCEPTED",
        )
        for i in range(n_entries)
    )
    return ModeloHistory(modelo=ModeloIdentifier(modelo), entries=entries)


def _save_two_histories(repo: ModeloHistoryRepository) -> tuple[ModeloHistory, ModeloHistory]:
    h130 = _make_history(modelo="130")
    h303 = _make_history(modelo="303")
    repo.save(h130)
    repo.save(h303)
    return h130, h303


@pytest.fixture
def repo() -> ModeloHistoryRepository:
    return ModeloHistoryRepository()


def _database_bytes(storage_root: Path) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(storage_root / "buckets" / "filing-test" / "db" / "aeat.db")


def _database_payloads(storage_root: Path) -> tuple[bytes, ...]:
    db_path = storage_root / "buckets" / "filing-test" / "db" / "aeat.db"
    with sqlite3.connect(db_path) as connection:
        return tuple(bytes(row[0]) for row in connection.execute("SELECT payload FROM secure_objects"))


class TestEmptyState:
    def test_load_returns_none_when_absent(self, repo: ModeloHistoryRepository) -> None:
        assert repo.load("130") is None

    def test_object_marker_identifies_secure_backend(self, repo: ModeloHistoryRepository) -> None:
        assert repo.envelope_path_for("130").as_posix().endswith("aeat.application.filing.history/130")


class TestSaveLoad:
    def test_round_trip(self, repo: ModeloHistoryRepository) -> None:
        history = _make_history(modelo="130")
        repo.save(history)
        loaded = ModeloHistoryRepository().load("130")
        assert loaded == history
        assert loaded is not None
        assert loaded.entries[0].period == Period.from_year_and_code(2026, "1T")

    def test_save_idempotent(self, repo: ModeloHistoryRepository) -> None:
        history = _make_history(modelo="130")
        repo.save(history)
        repo.save(history)
        assert repo.list_modelos() == ("130",)


class TestListIter:
    def test_list_modelos_sorted(self, repo: ModeloHistoryRepository) -> None:
        _save_two_histories(repo)
        assert repo.list_modelos() == ("130", "303")

    def test_iter_histories_yields_tuples(self, repo: ModeloHistoryRepository) -> None:
        h130, h303 = _save_two_histories(repo)
        loaded = dict(repo.iter_histories())
        assert loaded == {"130": h130, "303": h303}


class TestDelete:
    def test_delete_removes(self, repo: ModeloHistoryRepository) -> None:
        repo.save(_make_history(modelo="130"))
        assert repo.delete("130") is True
        assert repo.load("130") is None

    def test_delete_missing_returns_false(self, repo: ModeloHistoryRepository) -> None:
        assert repo.delete("nonexistent") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_audit_data(
        self,
        repo: ModeloHistoryRepository,
        _active_bucket_runtime: TestRuntimeProfile,
    ) -> None:
        repo.save(_make_history(modelo="130"))
        raw = _database_bytes(_active_bucket_runtime.storage_root)
        assert b"secure_objects" in raw
        payloads = _database_payloads(_active_bucket_runtime.storage_root)
        assert payloads
        for payload in payloads:
            assert b"2026Q1" not in payload
            assert b"2026 1T" not in payload
            assert b"ACCEPTED" not in payload
            assert b"130" not in payload

    def test_serialized_payload_stores_structured_period_not_combined_string(self) -> None:
        history = _make_history(modelo="130")
        dumped = history.model_dump(mode="json")
        assert dumped["entries"][0]["period"] == {"filing_year": 2026, "code": "1T"}
        assert "2026Q1" not in history.model_dump_json()

    def test_foreign_class_object_refused(self, repo: ModeloHistoryRepository) -> None:
        history = _make_history(modelo="130")
        bad = Envelope[ModeloHistory](
            schema_version=1,
            written_at=_FOREIGN_CLASS_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=history,
        )
        repo = ModeloHistoryRepository()
        SecureObjectRepository().save(
            namespace="aeat.application.filing.history",
            object_key="130",
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=bad.written_at,
            payload=bad.model_dump_json().encode("utf-8"),
        )
        with pytest.raises(ClassificationError):
            repo.load("130")


class TestUnsafeModelo:
    def test_unsafe_modelo_rejected(self, repo: ModeloHistoryRepository) -> None:
        for bad in ("", "..", ".", ".hidden", "../escape", "a/b", "a\\b"):
            with pytest.raises(ValueError):
                repo.envelope_path_for(bad)


class TestPerModeloLockIsolation:
    def test_lock_target_per_modelo(self, repo: ModeloHistoryRepository) -> None:
        a = repo.lock_target_for("130")
        b = repo.lock_target_for("303")
        assert a != b
        assert a.parent == b.parent
        assert a.parent == repo.store_dir
        assert a.as_posix().endswith("aeat.application.filing.history/130.lock")
        assert b.as_posix().endswith("aeat.application.filing.history/303.lock")
