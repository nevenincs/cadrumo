"""Unit tests for the read-only :class:`aeat.submission.SubmissionEngine`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from .....core.config import Settings
from . import (
    AuthProviderDescription,
    AuthProviderKind,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    LiveSubmitForbiddenError,
    SubmissionAttempt,
    SubmissionEngine,
    SubmissionError,
    SubmissionStatus,
    SubmittedFiling,
    make_submission_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


@dataclass
class _Draft(FilingDraftLike):
    draft_id: str = "draft-ut"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.APPROVED
    values: dict[str, str] = field(default_factory=dict)
    findings: tuple[FilingFinding, ...] = ()


class _OpenDeadlines:
    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        return True


class _OkAuthProvider:
    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(
            kind=self.kind,
            label="Test certificate",
            configured=True,
            available=True,
            identity_nif="X1234567L",
            subject="CN=Test",
            expires_on=date(2099, 12, 31),
            health_summary="OK:26800",
        )


def _build_engine(tmp_path: Path) -> SubmissionEngine:
    return SubmissionEngine(
        auth_provider=_OkAuthProvider(),
        deadline_checker=_OpenDeadlines(),
        settings=Settings(
            aeat_submissions_dir=tmp_path / "submissions",
            aeat_submission_browser_trace_dir=tmp_path / "traces",
        ),
    )


def _historical_filing(submission_id: str = "sub-1", modelo: str = "130") -> SubmittedFiling:
    now = datetime.now(UTC)
    return SubmittedFiling(
        submission_id=submission_id,
        draft_id="draft-1",
        modelo=modelo,
        period="2026Q1",
        profile_tax_id="X1234567L",
        status=SubmissionStatus.PENDING,
        submitted_at=now,
        attempts=(
            SubmissionAttempt(
                attempt_id="attempt-1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.PENDING,
            ),
        ),
    )


class TestPreflightOnly:
    def test_preflight_still_runs_without_transport(self, tmp_path: Path) -> None:
        _build_engine(tmp_path).preflight(_Draft(), today=date(2026, 4, 10))


class TestTransportRefusal:
    def test_transport_methods_are_not_exposed(self, tmp_path: Path) -> None:
        engine = _build_engine(tmp_path)
        assert not hasattr(engine, "submit_draft")
        assert not hasattr(engine, "submit_amendment")
        assert not (tmp_path / "submissions").exists()

    def test_legacy_transport_keywords_refuse(self, tmp_path: Path) -> None:
        with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
            SubmissionEngine(
                auth_provider=_OkAuthProvider(),
                deadline_checker=_OpenDeadlines(),
                settings=Settings(aeat_submissions_dir=tmp_path / "submissions"),
                browser_session_factory=object,
            )


class TestHistoricalRecords:
    def test_load_submission_roundtrip_for_existing_local_record(self, tmp_path: Path) -> None:
        engine = _build_engine(tmp_path)
        filing = _historical_filing(submission_id=make_submission_id("draft-1", 1))
        target = tmp_path / "submissions" / f"{filing.submission_id}.json"
        target.parent.mkdir(parents=True)
        target.write_text(filing.model_dump_json(indent=2), encoding="utf-8")
        assert engine.load_submission(filing.submission_id) == filing

    def test_load_submission_rejects_traversal_id(self, tmp_path: Path) -> None:
        engine = _build_engine(tmp_path)
        with pytest.raises(SubmissionError, match="simple filename token"):
            engine.load_submission("../escape")

    def test_list_filters_by_modelo(self, tmp_path: Path) -> None:
        engine = _build_engine(tmp_path)
        first = _historical_filing(submission_id="sub-1", modelo="130")
        second = _historical_filing(submission_id="sub-2", modelo="303")
        target_dir = tmp_path / "submissions"
        target_dir.mkdir()
        for filing in (first, second):
            (target_dir / f"{filing.submission_id}.json").write_text(
                filing.model_dump_json(indent=2),
                encoding="utf-8",
            )
        assert engine.list_submissions(modelo="130") == (first,)
        assert engine.list_submissions(modelo="999") == ()
