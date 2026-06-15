"""Tests for the governed-persistence SubmissionRepository."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.persistence.storage import (
    Envelope,
    SensitivityClass,
)
from ....adapters.persistence.storage.errors import ClassificationError
from ....adapters.persistence.storage.sql._orm import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....core import Period
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import (
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionStatus,
    make_submission_id,
)
from .._repository import (
    SubmissionRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = Period.from_year_and_code(2026, "1T")


def _make_filing(
    *,
    draft_id: str = "draft-abc123",
    attempt_ordinal: int = 1,
    status: SubmissionStatus = SubmissionStatus.PRESENTADA,
    period: Period | dict[str, object] = _PERIOD,
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
        period=period,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # test scaffolding: model boundary coerces Period|dict; dict/combined-string shapes are exercised by callers
        profile_tax_id="00000000T",
        status=status,
        submitted_at=submitted_at,
        attempts=(attempt,),
    )


@pytest.fixture(autouse=True)
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="submission-test") as profile:
        yield profile


def _database_bytes(runtime_profile: TestRuntimeProfile) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(runtime_profile.paths.db_dir / "aeat.db")


class TestEmptyState:
    def test_load_returns_none_when_absent(self) -> None:
        repo = SubmissionRepository()
        assert repo.load("missing-id") is None

    def test_object_marker_identifies_secure_backend(self) -> None:
        repo = SubmissionRepository()
        assert repo.envelope_path_for("abc123").as_posix().endswith("aeat.domain.submission.records/abc123")

    def test_list_submission_ids_empty(self) -> None:
        repo = SubmissionRepository()
        assert repo.list_submission_ids() == ()


class TestSaveLoad:
    def test_round_trip_preserves_payload(self) -> None:
        repo = SubmissionRepository()
        filing = _make_filing()
        repo.save(filing)

        repo_b = SubmissionRepository()
        loaded = repo_b.load(filing.submission_id)
        assert loaded == filing

    def test_save_is_idempotent(self) -> None:
        repo = SubmissionRepository()
        filing = _make_filing()
        repo.save(filing)
        repo.save(filing)
        assert repo.list_submission_ids() == (filing.submission_id,)

    def test_period_dict_round_trips_through_model_boundary(self) -> None:
        filing = _make_filing(period={"filing_year": 2026, "code": "1T"})

        assert filing.period == _PERIOD

    def test_combined_period_string_rejected_at_model_boundary(self) -> None:
        with pytest.raises(ValidationError, match="period"):
            _make_filing(period="2026Q1")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # negative test: combined period string must be rejected at the model boundary


class TestListAndIter:
    def test_list_returns_persisted_ids_sorted(self) -> None:
        repo = SubmissionRepository()
        f1 = _make_filing(draft_id="d-1", attempt_ordinal=1)
        f2 = _make_filing(draft_id="d-2", attempt_ordinal=1)
        repo.save(f1)
        repo.save(f2)
        ids = repo.list_submission_ids()
        assert set(ids) == {f1.submission_id, f2.submission_id}
        assert ids == tuple(sorted(ids))

    def test_iter_submissions_yields_payloads(self) -> None:
        repo = SubmissionRepository()
        f1 = _make_filing(draft_id="d-1", attempt_ordinal=1)
        f2 = _make_filing(draft_id="d-2", attempt_ordinal=1)
        repo.save(f1)
        repo.save(f2)
        loaded = {payload.submission_id: payload for payload in repo.iter_submissions()}
        assert loaded[f1.submission_id] == f1
        assert loaded[f2.submission_id] == f2

    def test_iter_submissions_skips_unreadable_rows_with_warning(
        self,
        runtime_profile: TestRuntimeProfile,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        repo = SubmissionRepository()
        healthy = _make_filing(draft_id="healthy", attempt_ordinal=1)
        future = _make_filing(draft_id="future", attempt_ordinal=1)
        repo.save(healthy)
        repo.save(future)

        with session_scope(runtime_profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == SubmissionRepository.namespace,
                    SecureObjectRow.object_key == future.submission_id,
                ),
            ).scalar_one()
            row.schema_version = SubmissionRepository.schema_version + 1

        caplog.set_level("WARNING")

        assert tuple(repo.iter_submissions()) == (healthy,)
        assert "skipping unreadable submission" in caplog.text
        assert "schema version 2 exceeds supported 1" in caplog.text


class TestDelete:
    def test_delete_removes_object(self) -> None:
        repo = SubmissionRepository()
        filing = _make_filing()
        repo.save(filing)
        assert repo.delete(filing.submission_id) is True
        assert repo.load(filing.submission_id) is None

    def test_delete_missing_returns_false(self) -> None:
        repo = SubmissionRepository()
        assert repo.delete("never-existed") is False


class TestClassificationGate:
    def test_database_payload_is_encrypted_audit_data(
        self,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        repo = SubmissionRepository()
        filing = _make_filing()
        repo.save(filing)
        raw = _database_bytes(runtime_profile)
        assert b"secure_objects" in raw
        assert b"00000000T" not in raw
        assert filing.submission_id.encode("utf-8") not in raw
        assert repo.load(filing.submission_id) == filing

    def test_foreign_class_object_refused(
        self,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        # Repository classifies at write time as well as load time:
        # the namespace-classification gate fires on save when the
        # supplied classification does not match the namespace
        # definition. Asserting the save-side refusal is sufficient.
        filing = _make_filing()
        bad = Envelope[ModeloPresentado](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=filing,
        )
        with pytest.raises(ClassificationError):
            runtime_profile.repository.save(
                namespace="aeat.domain.submission.records",
                object_key=filing.submission_id,
                classification=SensitivityClass.OPERATIONAL,
                schema_version=1,
                written_at=bad.written_at,
                payload=bad.model_dump_json().encode("utf-8"),
            )


class TestUnsafeSubmissionIds:
    @pytest.mark.parametrize(
        "bad",
        ["", "..", ".", ".hidden", "../escape", "a/b", "a\\b"],
    )
    def test_unsafe_id_rejected(self, bad: str) -> None:
        repo = SubmissionRepository()
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)


class TestPerSubmissionLockIsolation:
    def test_lock_target_per_submission(self) -> None:
        repo = SubmissionRepository()
        a = repo.lock_target_for("sub-a")
        b = repo.lock_target_for("sub-b")
        assert a != b
        assert a.parent == b.parent
        assert a.parent == repo.store_dir
        assert a.as_posix().endswith("aeat.domain.submission.records/sub-a.lock")
        assert b.as_posix().endswith("aeat.domain.submission.records/sub-b.lock")
