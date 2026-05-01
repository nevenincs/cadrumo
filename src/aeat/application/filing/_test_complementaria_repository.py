"""Tests for the governed-persistence FilingAmendmentRepository."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
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
from . import build_draft
from ...domain.filing._amendment import (
    AmendmentKind,
    CasillaChange,
    FilingAmendment,
)
from ...domain.filing._complementaria_repository import (
    AmendmentMigrationSummary,
    FilingAmendmentRepository,
    migrate_legacy_amendments_to_repository,
)
from .runtime import FilingOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> FilingOperatorProfile:
    return FilingOperatorProfile(
        tax_id="00000000T",
        display_name="Test Autónomo",
        applicable_modelos=("130",),
    )


def _make_amendment(*, amendment_id: str = "amend-001") -> FilingAmendment:
    amended_draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=_profile(),
        inputs={"01": 13000, "02": 3500, "05": 400, "06": 0},
        schema_provider=build_runtime_schema_provider(),
    )
    return FilingAmendment(
        amendment_id=amendment_id,
        submission_id="sub-abc",
        original_csv="CSV-ORIG-001",
        original_model="130",
        original_period="2026Q1",
        amendment_kind=AmendmentKind.COMPLEMENTARIA,
        delta=(
            CasillaChange(
                casilla_code="01",
                old_value=Decimal("12500"),
                new_value=Decimal("13000"),
                reason="Test correction.",
            ),
        ),
        amended_draft=amended_draft,
        created_at=datetime(2026, 4, 27, 10, 0, tzinfo=UTC),
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "amendments-store"


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
        repo = FilingAmendmentRepository(store_dir=store_dir)
        assert repo.load("missing-id") is None

    def test_envelope_path_under_store_dir(self, store_dir: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        assert repo.envelope_path_for("xyz") == store_dir / "xyz.envelope.json"


class TestSaveLoad:
    def test_round_trip(self, store_dir: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        amendment = _make_amendment()
        repo.save(amendment)
        loaded = FilingAmendmentRepository(store_dir=store_dir).load(amendment.amendment_id)
        assert loaded == amendment


class TestListIter:
    def test_list_and_iter(self, store_dir: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        a1 = _make_amendment(amendment_id="amend-a")
        a2 = _make_amendment(amendment_id="amend-b")
        repo.save(a1)
        repo.save(a2)
        ids = repo.list_amendment_ids()
        assert ids == ("amend-a", "amend-b")
        loaded = {a.amendment_id: a for a in repo.iter_amendments()}
        assert loaded == {a1.amendment_id: a1, a2.amendment_id: a2}


class TestDelete:
    def test_delete_removes(self, store_dir: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        amendment = _make_amendment()
        repo.save(amendment)
        assert repo.delete(amendment.amendment_id) is True
        assert repo.load(amendment.amendment_id) is None

    def test_delete_missing_returns_false(self, store_dir: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        assert repo.delete("nope") is False


class TestClassificationGate:
    def test_envelope_records_audit_class(self, store_dir: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        amendment = _make_amendment()
        repo.save(amendment)
        text = repo.envelope_path_for(amendment.amendment_id).read_text(encoding="utf-8")
        assert '"classification":"audit"' in text

    def test_foreign_class_envelope_refused(self, store_dir: Path) -> None:
        from ...adapters.persistence.storage import Envelope, SensitivityClass, save_encrypted_envelope
        from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        store_dir.mkdir(parents=True, exist_ok=True)
        amendment = _make_amendment()
        bad = Envelope[FilingAmendment](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=amendment,
        )
        repo = FilingAmendmentRepository(store_dir=store_dir)
        save_encrypted_envelope(
            bad,
            repo.envelope_path_for(amendment.amendment_id),
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=b"aeat.application.filing.amendment.v1",
        )
        with pytest.raises(ClassificationError):
            repo.load(amendment.amendment_id)


class TestUnsafeAmendmentIds:
    @pytest.mark.parametrize(
        "bad",
        ["", "..", ".", ".hidden", "../escape", "a/b", "a\\b"],
    )
    def test_unsafe_id_rejected(self, store_dir: Path, bad: str) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)


class TestMigration:
    def test_migrate_legacy(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-amendments"
        legacy_dir.mkdir()
        a1 = _make_amendment(amendment_id="amend-a")
        a2 = _make_amendment(amendment_id="amend-b")
        for amendment in (a1, a2):
            (legacy_dir / f"{amendment.amendment_id}.json").write_text(
                amendment.model_dump_json(),
                encoding="utf-8",
            )
        repo = FilingAmendmentRepository(store_dir=store_dir)
        summary = migrate_legacy_amendments_to_repository(legacy_dir, repository=repo)
        assert isinstance(summary, AmendmentMigrationSummary)
        assert summary.imported == 2
        assert summary.errors == 0
        assert set(repo.list_amendment_ids()) == {a1.amendment_id, a2.amendment_id}

    def test_re_migrate_skips_already_present(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-amendments"
        legacy_dir.mkdir()
        amendment = _make_amendment()
        (legacy_dir / f"{amendment.amendment_id}.json").write_text(
            amendment.model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingAmendmentRepository(store_dir=store_dir)
        first = migrate_legacy_amendments_to_repository(legacy_dir, repository=repo)
        assert first.imported == 1
        second = migrate_legacy_amendments_to_repository(legacy_dir, repository=repo)
        assert second.imported == 0
        assert second.skipped == 1

    def test_migrate_skips_unparseable(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-amendments"
        legacy_dir.mkdir()
        (legacy_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")
        amendment = _make_amendment()
        (legacy_dir / f"{amendment.amendment_id}.json").write_text(
            amendment.model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingAmendmentRepository(store_dir=store_dir)
        summary = migrate_legacy_amendments_to_repository(legacy_dir, repository=repo)
        assert summary.imported == 1
        assert summary.errors == 1

    def test_migrate_missing_dir_raises(self, store_dir: Path, tmp_path: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        with pytest.raises(FileNotFoundError):
            migrate_legacy_amendments_to_repository(tmp_path / "nope", repository=repo)


class TestMigrationLockedPerAmendment:
    def test_migration_blocked_by_held_lock(self, store_dir: Path, tmp_path: Path) -> None:
        from ...adapters.persistence.storage import exclusive_file_lock

        legacy_dir = tmp_path / "legacy-amendments"
        legacy_dir.mkdir()
        amendment = _make_amendment()
        (legacy_dir / f"{amendment.amendment_id}.json").write_text(
            amendment.model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingAmendmentRepository(store_dir=store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        with (
            exclusive_file_lock(repo.lock_target_for(amendment.amendment_id)),
            pytest.raises(LockAcquisitionError),
        ):
            migrate_legacy_amendments_to_repository(legacy_dir, repository=repo)
