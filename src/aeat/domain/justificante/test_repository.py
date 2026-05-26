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
    EphemeralMasterKeyProvider,
)
from aeat.adapters.persistence.storage.errors import ClassificationError
from aeat.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.core.config import load_settings, override_settings
from aeat.domain.justificante._repository import JustificanteRepository
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


@pytest.fixture(autouse=True)
def _active_runtime(tmp_path: Path) -> Iterator[None]:
    with override_settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile="justificante-test",
        aeat_secret_passphrase=load_settings().aeat_dev_test_database_password,
    ) as settings:
        dispose_engine(settings)
        provider = EphemeralMasterKeyProvider()
        try:
            with provider:
                yield
        finally:
            dispose_engine(settings)


def _database_bytes(tmp_path: Path) -> bytes:
    return (tmp_path / "buckets" / "justificante-test" / "db" / "aeat.db").read_bytes()


class TestEmptyState:
    def test_load_returns_none_when_absent(self) -> None:
        repo = JustificanteRepository()
        assert repo.load("DOESNOTEXIST") is None

    def test_object_marker_identifies_secure_backend(self) -> None:
        repo = JustificanteRepository()
        assert repo.envelope_path_for("CSV1234").as_posix().endswith("aeat.domain.justificante.metadata/CSV1234")


class TestSaveLoad:
    def test_round_trip(self, tmp_path: Path) -> None:
        repo = JustificanteRepository()
        record = _make_justificante(tmp_path)
        repo.save(record)
        loaded = JustificanteRepository().load(record.csv)
        assert loaded == record

    def test_save_idempotent(self, tmp_path: Path) -> None:
        repo = JustificanteRepository()
        record = _make_justificante(tmp_path)
        repo.save(record)
        repo.save(record)
        assert repo.list_csvs() == (record.csv,)


class TestListIter:
    def test_list_and_iter(self, tmp_path: Path) -> None:
        repo = JustificanteRepository()
        a = _make_justificante(tmp_path, csv="AAAA1111BBBB2222")
        b = _make_justificante(tmp_path, csv="CCCC3333DDDD4444")
        repo.save(a)
        repo.save(b)
        assert set(repo.list_csvs()) == {a.csv, b.csv}
        loaded = {r.csv: r for r in repo.iter_justificantes()}
        assert loaded == {a.csv: a, b.csv: b}


class TestDelete:
    def test_delete_removes(self, tmp_path: Path) -> None:
        repo = JustificanteRepository()
        record = _make_justificante(tmp_path)
        repo.save(record)
        assert repo.delete(record.csv) is True
        assert repo.load(record.csv) is None

    def test_delete_missing_returns_false(self) -> None:
        repo = JustificanteRepository()
        assert repo.delete("MISSING1234") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_audit_data(self, tmp_path: Path) -> None:
        repo = JustificanteRepository()
        record = _make_justificante(tmp_path)
        repo.save(record)
        raw = _database_bytes(tmp_path)
        assert b"secure_objects" in raw
        assert record.csv.encode("utf-8") not in raw
        assert b"00000000T" not in raw
        assert b"10.00" not in raw

    def test_foreign_class_object_refused(self, tmp_path: Path) -> None:
        from aeat.adapters.persistence.storage import Envelope, SensitivityClass

        record = _make_justificante(tmp_path)
        bad = Envelope[Justificante](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=record,
        )
        repo = JustificanteRepository()
        secure_object_repository_for_bucket("justificante-test").save(
            namespace="aeat.domain.justificante.metadata",
            object_key=record.csv,
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=bad.written_at,
            payload=bad.model_dump_json().encode("utf-8"),
        )
        with pytest.raises(ClassificationError):
            repo.load(record.csv)


class TestUnsafeCsv:
    @pytest.mark.parametrize(
        "bad",
        ["", "..", ".", ".hidden", "../escape", "a/b", "a\\b"],
    )
    def test_unsafe_csv_rejected(self, bad: str) -> None:
        repo = JustificanteRepository()
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)
