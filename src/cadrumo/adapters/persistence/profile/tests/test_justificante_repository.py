"""Tests for the governed-persistence JustificanteRepository."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from .....core.classification.policies import SensitivityClass
from .....core.period import Period
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_path
from .....domain.justificante import Justificante, JustificanteRepositoryProtocol
from .....tests.aeat_literal_fixtures import JUSTIFICANTE_VERIFY_PATH_FIXTURE, aeat_url
from .....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...storage.envelope._envelope import Envelope
from ...storage.errors import ClassificationError
from ..justificante import JustificanteRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_FOREIGN_CLASS_WRITTEN_AT = datetime(2026, 5, 26, 16, 0, 0, tzinfo=UTC)


def _make_justificante(
    tmp_path: Path,
    *,
    csv: str = "ABCD1234EFGH5678",
    period: object = "1T",
) -> Justificante:
    pdf = tmp_path / f"{csv}.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF\n")
    return Justificante.model_validate(
        {
            "csv": csv,
            "modelo": "130",
            "period": period,
            "ejercicio": "2026",
            "presentation_id": None,
            "presented_at": datetime(2026, 4, 10, 11, 23, 45, tzinfo=UTC),
            "tax_id": "00000000T",
            "total_a_ingresar": Decimal("10.00"),
            "total_a_devolver": None,
            "verification_url": TypeAdapter(AnyHttpUrl).validate_python(
                aeat_url("sede", JUSTIFICANTE_VERIFY_PATH_FIXTURE),
            ),
            "source_pdf_path": pdf,
            "source_pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "parsed_at": datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
        },
    )


def _save_two_justificantes(repo: JustificanteRepository, tmp_path: Path) -> tuple[Justificante, Justificante]:
    a = _make_justificante(tmp_path, csv="AAAA1111BBBB2222")
    b = _make_justificante(tmp_path, csv="CCCC3333DDDD4444")
    repo.save(a)
    repo.save(b)
    return a, b


@pytest.fixture(autouse=True)
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="562b3752-db22-4329-a58d-fb3b4df61e7d") as profile:
        yield profile


@pytest.fixture
def repo() -> JustificanteRepository:
    return JustificanteRepository()


def _database_bytes(runtime_profile: TestRuntimeProfile) -> bytes:
    from .....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(runtime_profile.paths.database_file)


class TestEmptyState:
    def test_repository_implements_domain_port(self, repo: JustificanteRepository) -> None:
        assert isinstance(repo, JustificanteRepositoryProtocol)

    def test_load_returns_none_when_absent(self, repo: JustificanteRepository) -> None:
        assert repo.load("DOESNOTEXIST") is None

    def test_object_marker_identifies_secure_backend(self, repo: JustificanteRepository) -> None:
        assert repo.envelope_path_for("CSV1234").as_posix().endswith("cadrumo.domain.justificante.metadata/CSV1234")


class TestSaveLoad:
    def test_round_trip(self, repo: JustificanteRepository, tmp_path: Path) -> None:
        record = _make_justificante(tmp_path)
        repo.save(record)
        loaded = JustificanteRepository().load(record.csv)
        assert loaded == record

    def test_annual_period_requires_bare_registry_token(self, tmp_path: Path) -> None:
        record = _make_justificante(tmp_path, period="0A")
        assert record.period == Period.from_year_and_code(2026, "0A")

    def test_bare_year_period_is_not_accepted_as_annual_token(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="Period"):
            _make_justificante(tmp_path, period="2026")

    def test_save_idempotent(self, repo: JustificanteRepository, tmp_path: Path) -> None:
        record = _make_justificante(tmp_path)
        repo.save(record)
        repo.save(record)
        assert repo.list_csvs() == (record.csv,)

    def test_save_persists_only_to_the_secure_database_object(
        self,
        repo: JustificanteRepository,
        tmp_path: Path,
    ) -> None:
        """A saved justificante never reaches the plaintext ``justificantes`` directory.

        :data:`StorageCategory.JUSTIFICANTES` now declares
        no consumer at all. Its only one was the master-key rotation sweep,
        deleted with the shared-master model it belonged to, and even then
        that module only walked the directory looking for ``.envelope.json``
        files to re-encrypt -- it was a sweep, never a writer. :class:`JustificanteRepository`'s own module
        docstring states "no plaintext metadata JSON or envelope file lands
        on disk"; this proves it, mirroring
        ``test_put_file_reads_source_but_persists_only_secure_database_object``
        for the attachments store. The assertion routes through
        :func:`storage_path` rather than a literal so a future taxonomy
        subpath move is tracked automatically instead of silently passing
        vacuously against a stale path.
        """
        record = _make_justificante(tmp_path)
        repo.save(record)

        assert repo.load(record.csv) == record
        assert not storage_path(StorageCategory.JUSTIFICANTES).exists()


class TestListIter:
    def test_list_and_iter(self, repo: JustificanteRepository, tmp_path: Path) -> None:
        a, b = _save_two_justificantes(repo, tmp_path)
        assert set(repo.list_csvs()) == {a.csv, b.csv}
        loaded = {r.csv: r for r in repo.iter_justificantes()}
        assert loaded == {a.csv: a, b.csv: b}


class TestDelete:
    def test_delete_removes(self, repo: JustificanteRepository, tmp_path: Path) -> None:
        record = _make_justificante(tmp_path)
        repo.save(record)
        assert repo.delete(record.csv) is True
        assert repo.load(record.csv) is None

    def test_delete_missing_returns_false(self, repo: JustificanteRepository) -> None:
        assert repo.delete("MISSING1234") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_audit_data(
        self,
        repo: JustificanteRepository,
        tmp_path: Path,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        record = _make_justificante(tmp_path)
        repo.save(record)
        raw = _database_bytes(runtime_profile)
        assert b"secure_objects" in raw
        assert record.csv.encode("utf-8") not in raw
        assert b"00000000T" not in raw
        assert b"10.00" not in raw

    def test_foreign_class_object_refused(
        self,
        tmp_path: Path,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        # Repository now classifies at write time as well as load time:
        # the namespace-classification gate fires on save when the
        # supplied classification does not match the namespace
        # definition. Asserting the save-side refusal is sufficient to
        # prove the gate is binding for foreign-class envelopes.
        record = _make_justificante(tmp_path)
        bad = Envelope[Justificante](
            schema_version=1,
            written_at=_FOREIGN_CLASS_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=record,
        )
        with pytest.raises(ClassificationError):
            runtime_profile.repository.save(
                namespace="cadrumo.domain.justificante.metadata",
                object_key=record.csv,
                classification=SensitivityClass.OPERATIONAL,
                schema_version=1,
                written_at=bad.written_at,
                payload=bad.model_dump_json().encode("utf-8"),
            )


class TestUnsafeCsv:
    def test_unsafe_csv_rejected(self, repo: JustificanteRepository) -> None:
        for bad in ("", "..", ".", ".hidden", "../escape", "a/b", "a\\b"):
            try:
                repo.envelope_path_for(bad)
            except ValueError:
                continue
            pytest.fail(f"unsafe justificante CSV {bad!r} was accepted")
