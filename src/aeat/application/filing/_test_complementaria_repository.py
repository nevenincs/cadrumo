"""Tests for the governed-persistence :class:`FilingAmendmentRepository`.

Exercises the round-trip save/load API, list/iter/delete behaviour,
the AUDIT classification gate, the unsafe-id rejection, the
per-amendment lock isolation of
:class:`aeat.domain.filing.FilingAmendmentRepository`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
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
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...domain.filing._amendment import (
    AmendmentKind,
    CasillaChange,
    FilingAmendment,
)
from ...domain.filing._complementaria_repository import (
    FilingAmendmentRepository,
)
from ...domain.filing._schema import FilingDraft, FilingDraftStatus, FilingValue, FilingValueKind, compute_draft_id

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _make_amendment(*, amendment_id: str = "amend-001") -> FilingAmendment:
    now = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    values = (
        FilingValue(
            casilla_id="01",
            value=Decimal("13000"),
            kind=FilingValueKind.LITERAL,
            source="test correction",
        ),
    )
    amended_draft = FilingDraft(
        draft_id=compute_draft_id(
            modelo="130",
            period="2026Q1",
            profile_tax_id="00000000T",
            schema_version="test-schema-v1",
            values=values,
        ),
        modelo="130",
        period="2026Q1",
        profile_tax_id="00000000T",
        status=FilingDraftStatus.VALIDATED,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version="test-schema-v1",
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
        created_at=now,
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "amendments-store"


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'aeat.db'}")
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
        dispose_engine()


def _database_bytes(tmp_path: Path) -> bytes:
    return (tmp_path / "aeat.db").read_bytes()


class TestEmptyState:
    def test_load_returns_none_when_absent(self, store_dir: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        assert repo.load("missing-id") is None

    def test_object_marker_identifies_secure_backend(self, store_dir: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        assert repo.envelope_path_for("xyz").as_posix().endswith("aeat.domain.filing.amendments/xyz")


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
    def test_database_payload_is_encrypted_audit_data(self, store_dir: Path, tmp_path: Path) -> None:
        repo = FilingAmendmentRepository(store_dir=store_dir)
        amendment = _make_amendment()
        repo.save(amendment)
        raw = _database_bytes(tmp_path)
        assert b"secure_objects" in raw
        assert b"CSV-ORIG-001" not in raw
        assert b"Test correction" not in raw
        assert amendment.amendment_id.encode("utf-8") not in raw

    def test_foreign_class_object_refused(self, store_dir: Path) -> None:
        from ...adapters.persistence.storage import Envelope, SensitivityClass

        amendment = _make_amendment()
        bad = Envelope[FilingAmendment](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=amendment,
        )
        repo = FilingAmendmentRepository(store_dir=store_dir)
        SecureObjectRepository().save(
            namespace="aeat.domain.filing.amendments",
            object_key=amendment.amendment_id,
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=bad.written_at,
            payload=bad.model_dump_json().encode("utf-8"),
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
