"""Tests for the governed-persistence FilingDraftRepository."""

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
from . import build_draft
from ._repository import (
    DraftMigrationSummary,
    FilingDraftRepository,
    migrate_legacy_drafts_to_repository,
)
from ._schema import FilingDraft
from .runtime import FilingOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> FilingOperatorProfile:
    return FilingOperatorProfile(
        tax_id="00000000T",
        display_name="Test Autónomo",
        applicable_modelos=("130", "303", "390"),
    )


def _make_draft(*, period: str = "2026Q1", ingresos: int = 12500) -> FilingDraft:
    return build_draft(
        modelo="130",
        period=period,
        profile=_profile(),
        inputs={"01": ingresos, "02": 3500, "05": 400, "06": 0},
        schema_provider=build_runtime_schema_provider(),
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
        from ...adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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
    """Phase-1 design: per-draft locks so concurrent saves of distinct drafts
    do not contend.

    We assert the lock TARGETS differ. That is enough to know the
    ``exclusive_file_lock`` calls operate on disjoint sidecars; lower-level
    concurrency is covered by the substrate's own lock tests.
    """

    def test_lock_target_per_draft(self, store_dir: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        a = repo.lock_target_for("draft-a")
        b = repo.lock_target_for("draft-b")
        assert a != b
        assert a.parent == store_dir
        assert b.parent == store_dir


class TestMigration:
    def test_migrate_legacy_drafts(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-drafts"
        legacy_dir.mkdir()
        d1 = _make_draft(period="2026Q1", ingresos=10000)
        d2 = _make_draft(period="2026Q2", ingresos=20000)
        for draft in (d1, d2):
            (legacy_dir / f"130_{draft.period}_{draft.draft_id}.json").write_text(
                draft.model_dump_json(),
                encoding="utf-8",
            )
        repo = FilingDraftRepository(store_dir=store_dir)
        summary = migrate_legacy_drafts_to_repository(legacy_dir, repository=repo)
        assert isinstance(summary, DraftMigrationSummary)
        assert summary.imported == 2
        assert summary.skipped == 0
        assert summary.errors == 0
        loaded_ids = set(repo.list_draft_ids())
        assert loaded_ids == {d1.draft_id, d2.draft_id}

    def test_re_migrate_skips_already_present(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-drafts"
        legacy_dir.mkdir()
        draft = _make_draft()
        (legacy_dir / f"130_{draft.period}_{draft.draft_id}.json").write_text(
            draft.model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingDraftRepository(store_dir=store_dir)
        first = migrate_legacy_drafts_to_repository(legacy_dir, repository=repo)
        assert first.imported == 1
        second = migrate_legacy_drafts_to_repository(legacy_dir, repository=repo)
        assert second.imported == 0
        assert second.skipped == 1

    def test_migrate_with_overwrite_replaces(self, store_dir: Path, tmp_path: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        original = _make_draft(ingresos=10000)
        repo.save(original)
        # Build a *different* draft with the same id by manually mutating
        # the JSON would break content-addressing; instead we just assert
        # overwrite=True does not raise on a non-empty destination.
        legacy_dir = tmp_path / "legacy-drafts"
        legacy_dir.mkdir()
        (legacy_dir / f"130_{original.period}_{original.draft_id}.json").write_text(
            original.model_dump_json(),
            encoding="utf-8",
        )
        summary = migrate_legacy_drafts_to_repository(
            legacy_dir,
            repository=repo,
            overwrite=True,
        )
        assert summary.imported == 1
        assert summary.skipped == 0

    def test_migrate_skips_unparseable_files(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-drafts"
        legacy_dir.mkdir()
        (legacy_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")
        valid = _make_draft()
        (legacy_dir / f"130_{valid.period}_{valid.draft_id}.json").write_text(
            valid.model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingDraftRepository(store_dir=store_dir)
        summary = migrate_legacy_drafts_to_repository(legacy_dir, repository=repo)
        assert summary.imported == 1
        assert summary.errors == 1

    def test_migrate_skips_existing_envelope_files(self, store_dir: Path, tmp_path: Path) -> None:
        """Re-running over a directory that already contains envelope files is a no-op."""
        legacy_dir = tmp_path / "legacy-drafts"
        legacy_dir.mkdir()
        # Place an envelope-suffix file in the legacy dir and ensure
        # the migration ignores it (no error, no double-count).
        (legacy_dir / "stray.envelope.json").write_text("{}", encoding="utf-8")
        valid = _make_draft()
        (legacy_dir / f"130_{valid.period}_{valid.draft_id}.json").write_text(
            valid.model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingDraftRepository(store_dir=store_dir)
        summary = migrate_legacy_drafts_to_repository(legacy_dir, repository=repo)
        assert summary.imported == 1
        assert summary.errors == 0

    def test_migrate_missing_dir_raises(self, store_dir: Path, tmp_path: Path) -> None:
        repo = FilingDraftRepository(store_dir=store_dir)
        with pytest.raises(FileNotFoundError):
            migrate_legacy_drafts_to_repository(tmp_path / "nope", repository=repo)


class TestMigrationLockedPerDraft:
    """The migration helper holds the per-draft lock for the duration of
    each save. A concurrent writer that holds the same per-draft lock
    must surface :class:`LockAcquisitionError`."""

    def test_migration_blocked_by_held_per_draft_lock(self, store_dir: Path, tmp_path: Path) -> None:
        from ...adapters.persistence.storage import exclusive_file_lock

        legacy_dir = tmp_path / "legacy-drafts"
        legacy_dir.mkdir()
        draft = _make_draft()
        (legacy_dir / f"130_{draft.period}_{draft.draft_id}.json").write_text(
            draft.model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingDraftRepository(store_dir=store_dir)
        # Pre-create the store dir so the lock target's parent exists.
        store_dir.mkdir(parents=True, exist_ok=True)
        with (
            exclusive_file_lock(repo.lock_target_for(draft.draft_id)),
            pytest.raises(LockAcquisitionError),
        ):
            migrate_legacy_drafts_to_repository(legacy_dir, repository=repo)


class TestSummaryFrozen:
    def test_summary_is_frozen(self, store_dir: Path, tmp_path: Path) -> None:
        from pydantic import ValidationError

        legacy_dir = tmp_path / "legacy-drafts"
        legacy_dir.mkdir()
        draft = _make_draft()
        (legacy_dir / f"130_{draft.period}_{draft.draft_id}.json").write_text(
            draft.model_dump_json(),
            encoding="utf-8",
        )
        repo = FilingDraftRepository(store_dir=store_dir)
        summary = migrate_legacy_drafts_to_repository(legacy_dir, repository=repo)
        with pytest.raises(ValidationError):
            summary.imported = 99  # type: ignore[misc]
