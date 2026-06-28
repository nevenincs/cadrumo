"""Tests for the governed-persistence :class:`SubmissionRepository`.

Exercises :class:`aeat.domain.submission.SubmissionRepository`'s save,
load, list, iter, and delete API; the per-submission lock isolation;
and the classification gate enforcement on the audit envelope.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core import Period
from .....domain.submission._models import (
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionStatus,
    make_submission_id,
)
from .....domain.submission._repository import (
    SubmissionRepository,
)
from .....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import (
    SensitivityClass,
)
from ..errors import ClassificationError
from ..sql.secure_objects import SecureObjectRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PERIOD = Period.from_year_and_code(2026, "1T")


def _make_filing(
    *,
    draft_id: str = "draft-abc123",
    attempt_ordinal: int = 1,
    status: SubmissionStatus = SubmissionStatus.PRESENTADA,
) -> ModeloPresentado:
    submitted_at = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    submission_id = make_submission_id(draft_id, attempt_ordinal)
    attempt = SubmissionAttempt(
        attempt_id=f"{submission_id}.{attempt_ordinal}",
        started_at=submitted_at,
        ended_at=submitted_at,
        status=status,
    )
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft_id,
        modelo="130",
        period=_PERIOD,
        profile_tax_id="00000000T",
        status=status,
        submitted_at=submitted_at,
        attempts=(attempt,),
    )


@pytest.fixture(autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile


def _database_bytes(profile: TestRuntimeProfile) -> bytes:
    from .....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(profile.paths.db_dir / "aeat.db")


@pytest.fixture
def repo() -> SubmissionRepository:
    return SubmissionRepository()


class TestEmptyState:
    def test_load_returns_none_when_absent(self, repo: SubmissionRepository) -> None:
        assert repo.load("missing-id") is None

    def test_object_marker_identifies_secure_backend(self, repo: SubmissionRepository) -> None:
        assert repo.envelope_path_for("abc123").as_posix().endswith("aeat.domain.submission.records/abc123")

    def test_list_submission_ids_empty(self, repo: SubmissionRepository) -> None:
        assert repo.list_submission_ids() == ()


class TestSaveLoad:
    def test_round_trip_preserves_payload(self, repo: SubmissionRepository) -> None:
        filing = _make_filing()
        repo.save(filing)

        repo_b = SubmissionRepository()
        loaded = repo_b.load(filing.submission_id)
        assert loaded == filing

    def test_save_is_idempotent(self, repo: SubmissionRepository) -> None:
        filing = _make_filing()
        repo.save(filing)
        repo.save(filing)
        assert repo.list_submission_ids() == (filing.submission_id,)


class TestListAndIter:
    def test_list_returns_persisted_ids_sorted(self, repo: SubmissionRepository) -> None:
        f1 = _make_filing(draft_id="d-1", attempt_ordinal=1)
        f2 = _make_filing(draft_id="d-2", attempt_ordinal=1)
        repo.save(f1)
        repo.save(f2)
        ids = repo.list_submission_ids()
        assert set(ids) == {f1.submission_id, f2.submission_id}
        assert ids == tuple(sorted(ids))

    def test_iter_submissions_yields_payloads(self, repo: SubmissionRepository) -> None:
        f1 = _make_filing(draft_id="d-1", attempt_ordinal=1)
        f2 = _make_filing(draft_id="d-2", attempt_ordinal=1)
        repo.save(f1)
        repo.save(f2)
        loaded = {payload.submission_id: payload for payload in repo.iter_submissions()}
        assert loaded[f1.submission_id] == f1
        assert loaded[f2.submission_id] == f2


class TestDelete:
    def test_delete_removes_object(self, repo: SubmissionRepository) -> None:
        filing = _make_filing()
        repo.save(filing)
        assert repo.delete(filing.submission_id) is True
        assert repo.load(filing.submission_id) is None

    def test_delete_missing_returns_false(self, repo: SubmissionRepository) -> None:
        assert repo.delete("never-existed") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_audit_data(
        self,
        _runtime_profile: TestRuntimeProfile,
        repo: SubmissionRepository,
    ) -> None:
        filing = _make_filing()
        repo.save(filing)
        raw = _database_bytes(_runtime_profile)
        assert b"secure_objects" in raw
        assert b"00000000T" not in raw
        assert filing.submission_id.encode("utf-8") not in raw
        assert repo.load(filing.submission_id) == filing

    def test_foreign_class_object_refused(self, repo: SubmissionRepository) -> None:
        from .. import Envelope

        filing = _make_filing()
        bad = Envelope[ModeloPresentado](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=filing,
        )
        repo = SubmissionRepository()
        SecureObjectRepository().save(
            namespace="aeat.domain.submission.records",
            object_key=filing.submission_id,
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=bad.written_at,
            payload=bad.model_dump_json().encode("utf-8"),
        )
        with pytest.raises(ClassificationError) as exc_info:
            repo.load(filing.submission_id)
        assert exc_info.value.translated_message == "errors.storage.namespace.classification_mismatch"
        assert exc_info.value.context == {
            "namespace": "aeat.domain.submission.records",
            "classification": SensitivityClass.OPERATIONAL.value,
            "expected": SensitivityClass.AUDIT.value,
        }


class TestUnsafeSubmissionIds:
    @pytest.mark.parametrize(
        "bad",
        ["", "..", ".", ".hidden", "../escape", "a/b", "a\\b"],
    )
    def test_unsafe_id_rejected(self, repo: SubmissionRepository, bad: str) -> None:
        with pytest.raises(ValueError, match=r"identifier|non-empty|submission_id"):
            repo.envelope_path_for(bad)


class TestPerSubmissionLockIsolation:
    def test_lock_target_per_submission(self, repo: SubmissionRepository) -> None:
        a = repo.lock_target_for("sub-a")
        b = repo.lock_target_for("sub-b")
        assert a != b
        assert a.parent == b.parent
        assert a.parent == repo.store_dir
        assert a.as_posix().endswith("aeat.domain.submission.records/sub-a.lock")
        assert b.as_posix().endswith("aeat.domain.submission.records/sub-b.lock")
