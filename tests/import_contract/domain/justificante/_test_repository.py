"""Tests for the governed-persistence JustificanteRepository."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    LockAcquisitionError,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from aeat.adapters.persistence.storage.errors import ClassificationError
from aeat.domain.justificante._repository import (
    JustificanteMigrationSummary,
    JustificanteRepository,
    migrate_legacy_justificantes_to_repository,
)
from aeat.domain.justificante._schema import Justificante

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _make_justificante(tmp_path: Path, *, csv: str = "ABCD1234EFGH5678") -> Justificante:
    pdf = tmp_path / f"{csv}.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF\n")
    return Justificante(
        csv=csv,
        modelo="130",
        period="1T",
        ejercicio="2026",
        presentation_id=None,
        presented_at=datetime(2026, 4, 10, 11, 23, 45, tzinfo=UTC),
        tax_id="00000000T",
        total_a_ingresar=Decimal("10.00"),
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python("https://sede.agenciatributaria.gob.es/verify"),
        source_pdf_path=pdf,
        source_pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
        parsed_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "justificantes-store"


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
        repo = JustificanteRepository(store_dir=store_dir)
        assert repo.load("DOESNOTEXIST") is None

    def test_envelope_path_under_store_dir(self, store_dir: Path) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        assert repo.envelope_path_for("CSV1234") == store_dir / "CSV1234.envelope.json"


class TestSaveLoad:
    def test_round_trip(self, store_dir: Path, tmp_path: Path) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        record = _make_justificante(tmp_path)
        repo.save(record)
        loaded = JustificanteRepository(store_dir=store_dir).load(record.csv)
        assert loaded == record

    def test_save_idempotent(self, store_dir: Path, tmp_path: Path) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        record = _make_justificante(tmp_path)
        repo.save(record)
        repo.save(record)
        assert repo.list_csvs() == (record.csv,)


class TestListIter:
    def test_list_and_iter(self, store_dir: Path, tmp_path: Path) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        a = _make_justificante(tmp_path, csv="AAAA1111BBBB2222")
        b = _make_justificante(tmp_path, csv="CCCC3333DDDD4444")
        repo.save(a)
        repo.save(b)
        assert set(repo.list_csvs()) == {a.csv, b.csv}
        loaded = {r.csv: r for r in repo.iter_justificantes()}
        assert loaded == {a.csv: a, b.csv: b}


class TestDelete:
    def test_delete_removes(self, store_dir: Path, tmp_path: Path) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        record = _make_justificante(tmp_path)
        repo.save(record)
        assert repo.delete(record.csv) is True
        assert repo.load(record.csv) is None

    def test_delete_missing_returns_false(self, store_dir: Path) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        assert repo.delete("MISSING1234") is False


class TestClassificationGate:
    def test_envelope_records_audit_class(self, store_dir: Path, tmp_path: Path) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        record = _make_justificante(tmp_path)
        repo.save(record)
        text = repo.envelope_path_for(record.csv).read_text(encoding="utf-8")
        assert '"classification":"audit"' in text

    def test_foreign_class_envelope_refused(self, store_dir: Path, tmp_path: Path) -> None:
        from aeat.adapters.persistence.storage import Envelope, SensitivityClass, save_encrypted_envelope
        from aeat.adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        store_dir.mkdir(parents=True, exist_ok=True)
        record = _make_justificante(tmp_path)
        bad = Envelope[Justificante](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=record,
        )
        repo = JustificanteRepository(store_dir=store_dir)
        save_encrypted_envelope(
            bad,
            repo.envelope_path_for(record.csv),
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=b"aeat.domain.justificante.metadata.v1",
        )
        with pytest.raises(ClassificationError):
            repo.load(record.csv)


class TestUnsafeCsv:
    @pytest.mark.parametrize(
        "bad",
        ["", "..", ".", ".hidden", "../escape", "a/b", "a\\b"],
    )
    def test_unsafe_csv_rejected(self, store_dir: Path, bad: str) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)


class TestMigration:
    def test_migrate_legacy(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-justificantes"
        legacy_dir.mkdir()
        a = _make_justificante(tmp_path, csv="AAAA1111BBBB2222")
        b = _make_justificante(tmp_path, csv="CCCC3333DDDD4444")
        for record in (a, b):
            (legacy_dir / f"{record.csv}.json").write_text(
                record.model_dump_json(),
                encoding="utf-8",
            )
        repo = JustificanteRepository(store_dir=store_dir)
        summary = migrate_legacy_justificantes_to_repository(legacy_dir, repository=repo)
        assert isinstance(summary, JustificanteMigrationSummary)
        assert summary.imported == 2
        assert summary.errors == 0
        assert set(repo.list_csvs()) == {a.csv, b.csv}

    def test_re_migrate_skips_already_present(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-justificantes"
        legacy_dir.mkdir()
        record = _make_justificante(tmp_path)
        (legacy_dir / f"{record.csv}.json").write_text(
            record.model_dump_json(),
            encoding="utf-8",
        )
        repo = JustificanteRepository(store_dir=store_dir)
        first = migrate_legacy_justificantes_to_repository(legacy_dir, repository=repo)
        assert first.imported == 1
        second = migrate_legacy_justificantes_to_repository(legacy_dir, repository=repo)
        assert second.imported == 0
        assert second.skipped == 1

    def test_migrate_skips_unparseable(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-justificantes"
        legacy_dir.mkdir()
        (legacy_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")
        record = _make_justificante(tmp_path)
        (legacy_dir / f"{record.csv}.json").write_text(
            record.model_dump_json(),
            encoding="utf-8",
        )
        repo = JustificanteRepository(store_dir=store_dir)
        summary = migrate_legacy_justificantes_to_repository(legacy_dir, repository=repo)
        assert summary.imported == 1
        assert summary.errors == 1

    def test_migrate_missing_dir_raises(self, store_dir: Path, tmp_path: Path) -> None:
        repo = JustificanteRepository(store_dir=store_dir)
        with pytest.raises(FileNotFoundError):
            migrate_legacy_justificantes_to_repository(tmp_path / "nope", repository=repo)


class TestMigrationLockedPerCsv:
    def test_migration_blocked_by_held_lock(self, store_dir: Path, tmp_path: Path) -> None:
        from aeat.adapters.persistence.storage import exclusive_file_lock

        legacy_dir = tmp_path / "legacy-justificantes"
        legacy_dir.mkdir()
        record = _make_justificante(tmp_path)
        (legacy_dir / f"{record.csv}.json").write_text(
            record.model_dump_json(),
            encoding="utf-8",
        )
        repo = JustificanteRepository(store_dir=store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        with (
            exclusive_file_lock(repo.lock_target_for(record.csv)),
            pytest.raises(LockAcquisitionError),
        ):
            migrate_legacy_justificantes_to_repository(legacy_dir, repository=repo)
