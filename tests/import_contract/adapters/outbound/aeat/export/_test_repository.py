"""Tests for the governed-persistence SubmissionRepository."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    LockAcquisitionError,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from aeat.adapters.persistence.storage.errors import ClassificationError
from aeat.domain.submission import (
    SubmissionAttempt,
    SubmissionStatus,
    SubmittedFiling,
    make_submission_id,
)
from aeat.domain.submission._repository import (
    SubmissionMigrationSummary,
    SubmissionRepository,
    migrate_legacy_submissions_to_repository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def _make_filing(
    *,
    draft_id: str = "draft-abc123",
    attempt_ordinal: int = 1,
    status: SubmissionStatus = SubmissionStatus.SUBMITTED,
) -> SubmittedFiling:
    submitted_at = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    submission_id = make_submission_id(draft_id, attempt_ordinal)
    attempt = SubmissionAttempt(
        attempt_id=f"{submission_id}.{attempt_ordinal}",
        started_at=submitted_at,
        ended_at=submitted_at,
        status=status,
    )
    return SubmittedFiling(
        submission_id=submission_id,
        draft_id=draft_id,
        modelo="130",
        period="2026Q1",
        profile_tax_id="00000000T",
        status=status,
        submitted_at=submitted_at,
        attempts=(attempt,),
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "submissions-store"


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
        repo = SubmissionRepository(store_dir=store_dir)
        assert repo.load("missing-id") is None

    def test_envelope_path_is_under_store_dir(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        assert repo.envelope_path_for("abc123") == store_dir / "abc123.envelope.json"

    def test_list_submission_ids_empty(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        assert repo.list_submission_ids() == ()


class TestSaveLoad:
    def test_round_trip_preserves_payload(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        filing = _make_filing()
        repo.save(filing)

        repo_b = SubmissionRepository(store_dir=store_dir)
        loaded = repo_b.load(filing.submission_id)
        assert loaded == filing

    def test_save_is_idempotent(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        filing = _make_filing()
        repo.save(filing)
        repo.save(filing)
        assert repo.list_submission_ids() == (filing.submission_id,)


class TestListAndIter:
    def test_list_returns_persisted_ids_sorted(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        f1 = _make_filing(draft_id="d-1", attempt_ordinal=1)
        f2 = _make_filing(draft_id="d-2", attempt_ordinal=1)
        repo.save(f1)
        repo.save(f2)
        ids = repo.list_submission_ids()
        assert set(ids) == {f1.submission_id, f2.submission_id}
        assert ids == tuple(sorted(ids))

    def test_iter_submissions_yields_payloads(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        f1 = _make_filing(draft_id="d-1", attempt_ordinal=1)
        f2 = _make_filing(draft_id="d-2", attempt_ordinal=1)
        repo.save(f1)
        repo.save(f2)
        loaded = {payload.submission_id: payload for payload in repo.iter_submissions()}
        assert loaded[f1.submission_id] == f1
        assert loaded[f2.submission_id] == f2


class TestDelete:
    def test_delete_removes_envelope(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        filing = _make_filing()
        repo.save(filing)
        assert repo.delete(filing.submission_id) is True
        assert repo.load(filing.submission_id) is None

    def test_delete_missing_returns_false(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        assert repo.delete("never-existed") is False


class TestClassificationGate:
    def test_envelope_records_audit_class(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        filing = _make_filing()
        repo.save(filing)
        envelope_text = repo.envelope_path_for(filing.submission_id).read_text(encoding="utf-8")
        assert '"classification":"audit"' in envelope_text

    def test_foreign_class_envelope_refused(self, store_dir: Path) -> None:
        from aeat.adapters.persistence.storage import Envelope, SensitivityClass, save_encrypted_envelope
        from aeat.adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

        store_dir.mkdir(parents=True, exist_ok=True)
        filing = _make_filing()
        bad = Envelope[SubmittedFiling](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=filing,
        )
        repo = SubmissionRepository(store_dir=store_dir)
        save_encrypted_envelope(
            bad,
            repo.envelope_path_for(filing.submission_id),
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=b"aeat.adapters.outbound.aeat.export.filing.v1",
        )
        with pytest.raises(ClassificationError):
            repo.load(filing.submission_id)


class TestUnsafeSubmissionIds:
    @pytest.mark.parametrize(
        "bad",
        ["", "..", ".", ".hidden", "../escape", "a/b", "a\\b"],
    )
    def test_unsafe_id_rejected(self, store_dir: Path, bad: str) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)


class TestPerSubmissionLockIsolation:
    def test_lock_target_per_submission(self, store_dir: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        a = repo.lock_target_for("sub-a")
        b = repo.lock_target_for("sub-b")
        assert a != b
        assert a.parent == store_dir
        assert b.parent == store_dir


class TestMigration:
    def test_migrate_legacy_submissions(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-submissions"
        legacy_dir.mkdir()
        f1 = _make_filing(draft_id="d-1", attempt_ordinal=1)
        f2 = _make_filing(draft_id="d-2", attempt_ordinal=1)
        for filing in (f1, f2):
            (legacy_dir / f"{filing.submission_id}.json").write_text(
                filing.model_dump_json(),
                encoding="utf-8",
            )
        repo = SubmissionRepository(store_dir=store_dir)
        summary = migrate_legacy_submissions_to_repository(legacy_dir, repository=repo)
        assert isinstance(summary, SubmissionMigrationSummary)
        assert summary.imported == 2
        assert summary.errors == 0
        assert set(repo.list_submission_ids()) == {f1.submission_id, f2.submission_id}

    def test_migrate_skips_subdirectories(self, store_dir: Path, tmp_path: Path) -> None:
        """``aeat_submissions_dir/amendment-results/`` has a different payload type;
        the migration helper must ignore it (sub-directories are skipped by iterdir
        is_file guard)."""
        legacy_dir = tmp_path / "legacy-submissions"
        legacy_dir.mkdir()
        (legacy_dir / "amendment-results").mkdir()
        (legacy_dir / "amendment-results" / "should-be-ignored.json").write_text("garbage", encoding="utf-8")
        filing = _make_filing()
        (legacy_dir / f"{filing.submission_id}.json").write_text(
            filing.model_dump_json(),
            encoding="utf-8",
        )
        repo = SubmissionRepository(store_dir=store_dir)
        summary = migrate_legacy_submissions_to_repository(legacy_dir, repository=repo)
        assert summary.imported == 1
        assert summary.errors == 0

    def test_re_migrate_skips_already_present(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-submissions"
        legacy_dir.mkdir()
        filing = _make_filing()
        (legacy_dir / f"{filing.submission_id}.json").write_text(
            filing.model_dump_json(),
            encoding="utf-8",
        )
        repo = SubmissionRepository(store_dir=store_dir)
        first = migrate_legacy_submissions_to_repository(legacy_dir, repository=repo)
        assert first.imported == 1
        second = migrate_legacy_submissions_to_repository(legacy_dir, repository=repo)
        assert second.imported == 0
        assert second.skipped == 1

    def test_migrate_skips_unparseable_files(self, store_dir: Path, tmp_path: Path) -> None:
        legacy_dir = tmp_path / "legacy-submissions"
        legacy_dir.mkdir()
        (legacy_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")
        filing = _make_filing()
        (legacy_dir / f"{filing.submission_id}.json").write_text(
            filing.model_dump_json(),
            encoding="utf-8",
        )
        repo = SubmissionRepository(store_dir=store_dir)
        summary = migrate_legacy_submissions_to_repository(legacy_dir, repository=repo)
        assert summary.imported == 1
        assert summary.errors == 1

    def test_migrate_missing_dir_raises(self, store_dir: Path, tmp_path: Path) -> None:
        repo = SubmissionRepository(store_dir=store_dir)
        with pytest.raises(FileNotFoundError):
            migrate_legacy_submissions_to_repository(tmp_path / "nope", repository=repo)


class TestMigrationLockedPerSubmission:
    """The migration helper holds the per-submission lock for the duration
    of each save."""

    def test_migration_blocked_by_held_lock(self, store_dir: Path, tmp_path: Path) -> None:
        from aeat.adapters.persistence.storage import exclusive_file_lock

        legacy_dir = tmp_path / "legacy-submissions"
        legacy_dir.mkdir()
        filing = _make_filing()
        (legacy_dir / f"{filing.submission_id}.json").write_text(
            filing.model_dump_json(),
            encoding="utf-8",
        )
        repo = SubmissionRepository(store_dir=store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        with (
            exclusive_file_lock(repo.lock_target_for(filing.submission_id)),
            pytest.raises(LockAcquisitionError),
        ):
            migrate_legacy_submissions_to_repository(legacy_dir, repository=repo)
