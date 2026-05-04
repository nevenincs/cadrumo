"""Tests for the governed-persistence :class:`FilingHistoryRepository`.

Exercises round-trip save/load, list/iter, deletion, the AUDIT
classification gate, unsafe-modelo rejection, and the per-modelo lock
isolation guarantees.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ...adapters.persistence.storage.errors import ClassificationError
from ...domain.sync import ModeloIdentifier, WireFilingEntry, WireFilingHistory
from ._history_repository import FilingHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _make_history(*, modelo: str = "130", n_entries: int = 2) -> WireFilingHistory:
    base = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    entries = tuple(
        WireFilingEntry(
            modelo=ModeloIdentifier(modelo),
            period=f"2026Q{i + 1}",
            submitted_at=base.replace(month=1 + 3 * i),
            status="ACCEPTED",
        )
        for i in range(n_entries)
    )
    return WireFilingHistory(entries=entries)


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "history-store"


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


class TestEmptyState:
    def test_load_returns_none_when_absent(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        assert repo.load("130") is None

    def test_envelope_path_under_store_dir(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        assert repo.envelope_path_for("130") == store_dir / "130.envelope.json"


class TestSaveLoad:
    def test_round_trip(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        history = _make_history(modelo="130")
        repo.save("130", history)
        loaded = FilingHistoryRepository(store_dir=store_dir).load("130")
        assert loaded == history

    def test_save_idempotent(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        history = _make_history(modelo="130")
        repo.save("130", history)
        repo.save("130", history)
        assert repo.list_modelos() == ("130",)


class TestListIter:
    def test_list_modelos_sorted(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        repo.save("303", _make_history(modelo="303"))
        repo.save("130", _make_history(modelo="130"))
        assert repo.list_modelos() == ("130", "303")

    def test_iter_histories_yields_tuples(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        h130 = _make_history(modelo="130")
        h303 = _make_history(modelo="303")
        repo.save("130", h130)
        repo.save("303", h303)
        loaded = dict(repo.iter_histories())
        assert loaded == {"130": h130, "303": h303}


class TestDelete:
    def test_delete_removes(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        repo.save("130", _make_history(modelo="130"))
        assert repo.delete("130") is True
        assert repo.load("130") is None

    def test_delete_missing_returns_false(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        assert repo.delete("nonexistent") is False


class TestClassificationGate:
    def test_envelope_records_audit_class(self, store_dir: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        repo.save("130", _make_history(modelo="130"))
        text = repo.envelope_path_for("130").read_text(encoding="utf-8")
        assert '"classification":"audit"' in text

    def test_foreign_class_envelope_refused(self, store_dir: Path) -> None:
        from ...adapters.persistence.storage import Envelope, SensitivityClass, save_encrypted_envelope
        from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        store_dir.mkdir(parents=True, exist_ok=True)
        history = _make_history(modelo="130")
        bad = Envelope[WireFilingHistory](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=history,
        )
        repo = FilingHistoryRepository(store_dir=store_dir)
        save_encrypted_envelope(
            bad,
            repo.envelope_path_for("130"),
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=b"aeat.application.filing.history.v1",
        )
        with pytest.raises(ClassificationError):
            repo.load("130")


class TestUnsafeModelo:
    @pytest.mark.parametrize(
        "bad",
        ["", "..", ".", ".hidden", "../escape", "a/b", "a\\b"],
    )
    def test_unsafe_modelo_rejected(self, store_dir: Path, bad: str) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)
