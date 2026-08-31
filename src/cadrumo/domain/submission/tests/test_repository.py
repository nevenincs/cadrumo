"""Tests for the governed-persistence SubmissionRepository."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.persistence.profile.submission import (
    SubmissionRepository,
)
from ....adapters.persistence.storage.envelope.contract import Envelope
from ....adapters.persistence.storage.errors import ClassificationError
from ....adapters.persistence.storage.sql._orm import SecureObjectRow
from ....adapters.persistence.storage.sql.engine import get_engine
from ....adapters.persistence.storage.sql.session import session_scope
from ....core.classification.policies import SensitivityClass
from ....core.period import Period
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._models import ModeloPresentado, SubmissionAttempt, SubmissionStatus, make_submission_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The capsule authority resolves a bucket id as a UUID, so a readable slug
#: cannot stand in for one. Matches the constant sibling suites declare.
_BUCKET_ID = "3f2a91c4-6d5e-4a7b-9c81-0e4d2b6f8a13"
_PERIOD = Period.from_year_and_code(2026, "1T")
_FOREIGN_CLASS_WRITTEN_AT = datetime(2026, 5, 26, 15, 30, 0, tzinfo=UTC)


def _make_filing(
    *,
    draft_id: str = "draft-abc123",
    attempt_ordinal: int = 1,
    status: SubmissionStatus = SubmissionStatus.PRESENTADA,
    profile_tax_id: str = "00000000T",
    period: object = _PERIOD,
) -> ModeloPresentado:
    submitted_at = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    submission_id = make_submission_id(draft_id, attempt_ordinal)
    attempt = SubmissionAttempt(
        attempt_id=f"{submission_id}.{attempt_ordinal}",
        started_at=submitted_at,
        ended_at=submitted_at,
        status=status,
    )
    return ModeloPresentado.model_validate(
        {
            "submission_id": submission_id,
            "draft_id": draft_id,
            "modelo": "130",
            "period": period,
            "profile_tax_id": profile_tax_id,
            "status": status,
            "submitted_at": submitted_at,
            "attempts": (attempt,),
        },
    )


def _save_two_filings(repo: SubmissionRepository) -> tuple[ModeloPresentado, ModeloPresentado]:
    f1 = _make_filing(draft_id="d-1", attempt_ordinal=1)
    f2 = _make_filing(draft_id="d-2", attempt_ordinal=1)
    repo.save(f1)
    repo.save(f2)
    return f1, f2


@pytest.fixture(autouse=True)
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def repo() -> SubmissionRepository:
    return SubmissionRepository()


def _database_bytes(runtime_profile: TestRuntimeProfile) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(runtime_profile.paths.database_file)


class TestEmptyState:
    def test_load_returns_none_when_absent(self, repo: SubmissionRepository) -> None:
        assert repo.load("missing-id") is None

    def test_object_marker_identifies_secure_backend(self, repo: SubmissionRepository) -> None:
        assert repo.envelope_path_for("abc123").as_posix().endswith("cadrumo.domain.submission.records/abc123")

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

    def test_period_dict_round_trips_through_model_boundary(self) -> None:
        filing = _make_filing(period={"filing_year": 2026, "code": "1T"})

        assert filing.period == _PERIOD

    def test_profile_tax_id_checksum_rejected_at_model_boundary(self) -> None:
        with pytest.raises(ValidationError, match="profile_tax_id"):
            _make_filing(profile_tax_id="12345678A")

    def test_combined_period_string_rejected_at_model_boundary(self) -> None:
        with pytest.raises(ValidationError, match="period"):
            _make_filing(period="2026Q1")


class TestListAndIter:
    def test_list_returns_persisted_ids_sorted(self, repo: SubmissionRepository) -> None:
        f1, f2 = _save_two_filings(repo)
        ids = repo.list_submission_ids()
        assert set(ids) == {f1.submission_id, f2.submission_id}
        assert ids == tuple(sorted(ids))

    def test_iter_submissions_yields_payloads(self, repo: SubmissionRepository) -> None:
        f1, f2 = _save_two_filings(repo)
        loaded = {payload.submission_id: payload for payload in repo.iter_submissions()}
        assert loaded[f1.submission_id] == f1
        assert loaded[f2.submission_id] == f2

    def test_iter_submissions_skips_unreadable_rows_with_warning(
        self,
        repo: SubmissionRepository,
        runtime_profile: TestRuntimeProfile,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        healthy = _make_filing(draft_id="healthy", attempt_ordinal=1)
        future = _make_filing(draft_id="future", attempt_ordinal=1)
        repo.save(healthy)
        repo.save(future)

        with session_scope(get_engine(runtime_profile.settings)) as session:
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
        assert "más reciente de lo que admite esta aplicación" in caplog.text


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
        repo: SubmissionRepository,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
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
            written_at=_FOREIGN_CLASS_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=filing,
        )
        with pytest.raises(ClassificationError):
            runtime_profile.repository.save(
                namespace="cadrumo.domain.submission.records",
                object_key=filing.submission_id,
                classification=SensitivityClass.OPERATIONAL,
                schema_version=1,
                written_at=bad.written_at,
                payload=bad.model_dump_json().encode("utf-8"),
            )


class TestUnsafeSubmissionIds:
    def test_unsafe_id_rejected(self, repo: SubmissionRepository) -> None:
        for bad in ("", "..", ".", ".hidden", "../escape", "a/b", "a\\b"):
            try:
                repo.envelope_path_for(bad)
            except ValueError:
                continue
            pytest.fail(f"unsafe submission id {bad!r} was accepted")


class TestPerSubmissionLockIsolation:
    def test_lock_target_per_submission(self, repo: SubmissionRepository) -> None:
        a = repo.lock_target_for("sub-a")
        b = repo.lock_target_for("sub-b")
        assert a != b
        assert a.parent == b.parent
        assert a.parent == repo.store_dir
        assert a.as_posix().endswith("cadrumo.domain.submission.records/sub-a.lock")
        assert b.as_posix().endswith("cadrumo.domain.submission.records/sub-b.lock")
