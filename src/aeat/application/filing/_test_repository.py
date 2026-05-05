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
from ...domain.filing._repository import FilingDraftRepository
from ...domain.filing._schema import FilingDraft
from .testing import build_registry_filing_draft

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _make_draft(*, period: str = "2026Q1", ingresos: int = 12500) -> FilingDraft:
    return build_registry_filing_draft(
        modelo="130",
        period=period,
        casilla_values={
            "01": Decimal(ingresos),
            "02": Decimal("3500"),
            "05": Decimal("400"),
            "06": Decimal("0"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        profile_tax_id="00000000T",
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "drafts-store"


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
        repo = FilingDraftRepository(store_dir=store_dir)
        assert repo.load("does-not-exist") is None

    def test_envelope_path_is_under_store_dir(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        assert repo.envelope_path_for("abc123") == store_dir / "abc123.envelope.json"

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

    def test_list_ignores_non_envelope_files(self, store_dir: Path) -> None:
        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / "stray.json").write_text("{}", encoding="utf-8")
        (store_dir / "stray.txt").write_text("x", encoding="utf-8")
        repo = FilingDraftRepository(store_dir=store_dir)
        repo.save(_make_draft())
        ids = repo.list_draft_ids()
        assert len(ids) == 1


class TestDelete:
    def test_delete_removes_envelope(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        draft = _make_draft()
        repo.save(draft)
        assert repo.delete(draft.draft_id) is True
        assert repo.load(draft.draft_id) is None

    def test_delete_missing_returns_false(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        assert repo.delete("never-existed") is False


class TestClassificationGate:
    def test_envelope_records_financial_class(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        draft = _make_draft()
        repo.save(draft)
        envelope_text = repo.envelope_path_for(draft.draft_id).read_text(encoding="utf-8")
        assert '"classification":"financial"' in envelope_text

    def test_foreign_class_envelope_refused(self, store_dir: Path) -> None:
        from ...adapters.persistence.storage import Envelope, SensitivityClass, save_encrypted_envelope
        from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        store_dir.mkdir(parents=True, exist_ok=True)
        draft = _make_draft()
        bad = Envelope[FilingDraft](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=draft,
        )
        repo = FilingDraftRepository(store_dir=store_dir)
        save_encrypted_envelope(
            bad,
            repo.envelope_path_for(draft.draft_id),
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=b"aeat.application.filing.draft.v1",
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
        assert a.parent == store_dir
        assert b.parent == store_dir
