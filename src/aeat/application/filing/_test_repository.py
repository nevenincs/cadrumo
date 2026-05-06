"""Tests for the governed-persistence :class:`FilingDraftRepository`.

Exercises round-trip save/load, idempotent saves, list/iter and stray
file filtering, deletion, the FINANCIAL classification gate, the
unsafe-id rejection, and the per-draft lock isolation.
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
from ...domain.filing._repository import FilingDraftRepository
from ...domain.filing._schema import FilingDraft, FilingDraftStatus, FilingValue, FilingValueKind, compute_draft_id

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _make_draft(*, period: str = "2026Q1", ingresos: int = 12500) -> FilingDraft:
    now = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    values = (
        FilingValue(
            casilla_id="01",
            value=Decimal(ingresos),
            kind=FilingValueKind.LITERAL,
            source="test input",
        ),
    )
    draft_id = compute_draft_id(
        modelo="130",
        period=period,
        profile_tax_id="00000000T",
        schema_version="test-schema-v1",
        values=values,
    )
    return FilingDraft(
        draft_id=draft_id,
        modelo="130",
        period=period,
        profile_tax_id="00000000T",
        status=FilingDraftStatus.VALIDATED,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version="test-schema-v1",
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "drafts-store"


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
        repo = FilingDraftRepository(store_dir=store_dir)
        assert repo.load("does-not-exist") is None

    def test_object_marker_identifies_secure_backend(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        assert repo.envelope_path_for("abc123").as_posix().endswith("aeat.domain.filing.drafts/abc123")

    def test_list_draft_ids_empty(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        assert repo.list_draft_ids() == ()


class TestSaveLoad:
    def test_round_trip_preserves_payload(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        draft = _make_draft()
        repo.save(draft)

        repo_b = FilingDraftRepository(store_dir=store_dir)
        loaded = repo_b.load(draft.draft_id)
        assert loaded == draft

    def test_save_is_idempotent(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        draft = _make_draft()
        repo.save(draft)
        repo.save(draft)
        assert repo.list_draft_ids() == (draft.draft_id,)


class TestListAndIter:
    def test_list_returns_persisted_ids_sorted(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        d1 = _make_draft(period="2026Q1", ingresos=10000)
        d2 = _make_draft(period="2026Q2", ingresos=20000)
        repo.save(d1)
        repo.save(d2)
        ids = repo.list_draft_ids()
        assert set(ids) == {d1.draft_id, d2.draft_id}
        assert ids == tuple(sorted(ids))

    def test_iter_drafts_yields_payloads(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        d1 = _make_draft(period="2026Q1", ingresos=10000)
        d2 = _make_draft(period="2026Q2", ingresos=20000)
        repo.save(d1)
        repo.save(d2)
        loaded = {payload.draft_id: payload for payload in repo.iter_drafts()}
        assert loaded[d1.draft_id] == d1
        assert loaded[d2.draft_id] == d2

    def test_list_ignores_plain_files_next_to_legacy_store_dir(self, store_dir: Path) -> None:
        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / "stray.json").write_text("{}", encoding="utf-8")
        (store_dir / "stray.txt").write_text("x", encoding="utf-8")
        repo = FilingDraftRepository(store_dir=store_dir)
        repo.save(_make_draft())
        ids = repo.list_draft_ids()
        assert len(ids) == 1


class TestDelete:
    def test_delete_removes_object(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        draft = _make_draft()
        repo.save(draft)
        assert repo.delete(draft.draft_id) is True
        assert repo.load(draft.draft_id) is None

    def test_delete_missing_returns_false(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        assert repo.delete("never-existed") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_financial_data(self, store_dir: Path, tmp_path: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        draft = _make_draft()
        repo.save(draft)
        raw = _database_bytes(tmp_path)
        assert b"secure_objects" in raw
        assert b"00000000T" not in raw
        assert b"2026Q1" not in raw
        assert draft.draft_id.encode("utf-8") not in raw

    def test_foreign_class_object_refused(self, store_dir: Path) -> None:
        from ...adapters.persistence.storage import Envelope, SensitivityClass

        draft = _make_draft()
        bad = Envelope[FilingDraft](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=draft,
        )
        repo = FilingDraftRepository(store_dir=store_dir)
        SecureObjectRepository().save(
            namespace="aeat.domain.filing.drafts",
            object_key=draft.draft_id,
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=bad.written_at,
            payload=bad.model_dump_json().encode("utf-8"),
        )
        with pytest.raises(ClassificationError):
            repo.load(draft.draft_id)


class TestUnsafeDraftIds:
    """Per-draft envelope paths must not compose into traversal."""

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "..",
            ".",
            ".hidden",
            "../escape",
            "a/b",
            "a\\b",
        ],
    )
    def test_unsafe_draft_id_rejected(self, store_dir: Path, bad: str) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)


class TestPerDraftLockIsolation:
    """Per-draft locks so concurrent saves of distinct drafts do not contend.

    Asserts the lock targets differ. That is enough to know the
    ``exclusive_file_lock`` calls operate on disjoint sidecars;
    lower-level concurrency is covered by the substrate's own lock
    tests.
    """

    def test_lock_target_per_draft(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        a = repo.lock_target_for("draft-a")
        b = repo.lock_target_for("draft-b")
        assert a != b
        assert a.parent == b.parent
