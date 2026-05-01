"""Tests for the governed-persistence FilingHistoryRepository."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    LockAcquisitionError,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ...adapters.persistence.storage.errors import ClassificationError
from ..sync import WireFilingEntry, WireFilingHistory
from ..sync._protocols import ModeloIdentifier
from ._history_repository import (
    FilingHistoryRepository,
    HistoryMigrationSummary,
    migrate_legacy_filing_history_to_repository,
)

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
        from ...adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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


class TestMigration:
    def test_migrate_legacy(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-history"
        legacy_dir.mkdir()
        h130 = _make_history(modelo="130")
        h303 = _make_history(modelo="303")
        for modelo, history in (("130", h130), ("303", h303)):
            (legacy_dir / f"{modelo}.json").write_text(
                history.model_dump_json(),
                encoding="utf-8",
            )
        repo = FilingHistoryRepository(store_dir=store_dir)
        summary = migrate_legacy_filing_history_to_repository(legacy_dir, repository=repo)
        assert isinstance(summary, HistoryMigrationSummary)
        assert summary.imported == 2
        assert summary.errors == 0
        assert set(repo.list_modelos()) == {"130", "303"}

    def test_migrate_skips_pages_subdir(self, store_dir: Path, tmp_path: Path) -> None:
        """The legacy `pages/` sub-directory carries archived HTML — must be skipped."""
        legacy_dir = tmp_path / "legacy-history"
        legacy_dir.mkdir()
        pages = legacy_dir / "pages"
        pages.mkdir()
        (pages / "junk.json").write_text("garbage", encoding="utf-8")
        h130 = _make_history(modelo="130")
        (legacy_dir / "130.json").write_text(h130.model_dump_json(), encoding="utf-8")
        repo = FilingHistoryRepository(store_dir=store_dir)
        summary = migrate_legacy_filing_history_to_repository(legacy_dir, repository=repo)
        assert summary.imported == 1
        assert summary.errors == 0

    def test_re_migrate_skips_already_present(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-history"
        legacy_dir.mkdir()
        (legacy_dir / "130.json").write_text(
            _make_history(modelo="130").model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingHistoryRepository(store_dir=store_dir)
        first = migrate_legacy_filing_history_to_repository(legacy_dir, repository=repo)
        assert first.imported == 1
        second = migrate_legacy_filing_history_to_repository(legacy_dir, repository=repo)
        assert second.imported == 0
        assert second.skipped == 1

    def test_migrate_skips_unparseable(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-history"
        legacy_dir.mkdir()
        (legacy_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")
        (legacy_dir / "130.json").write_text(
            _make_history(modelo="130").model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingHistoryRepository(store_dir=store_dir)
        summary = migrate_legacy_filing_history_to_repository(legacy_dir, repository=repo)
        assert summary.imported == 1
        assert summary.errors == 1

    def test_migrate_missing_dir_raises(self, store_dir: Path, tmp_path: Path) -> None:
        repo = FilingHistoryRepository(store_dir=store_dir)
        with pytest.raises(FileNotFoundError):
            migrate_legacy_filing_history_to_repository(tmp_path / "nope", repository=repo)


class TestMigrationLockedPerModelo:
    def test_migration_blocked_by_held_lock(self, store_dir: Path, tmp_path: Path) -> None:
        from ...adapters.persistence.storage import exclusive_file_lock

        legacy_dir = tmp_path / "legacy-history"
        legacy_dir.mkdir()
        (legacy_dir / "130.json").write_text(
            _make_history(modelo="130").model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingHistoryRepository(store_dir=store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        with (
            exclusive_file_lock(repo.lock_target_for("130")),
            pytest.raises(LockAcquisitionError),
        ):
            migrate_legacy_filing_history_to_repository(legacy_dir, repository=repo)
