"""Unit tests for the read-only :class:`aeat.adapters.outbound.aeat.export.SubmissionEngine`.

Exercises preflight-only behaviour, transport-refusal guards, and the
historical-records loader. The engine never opens a write transport;
these tests pin that contract structurally.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from ......application.auth import AuthProviderDescription, AuthProviderKind
from ......core import Period
from ......core.config import Settings
from ......domain.submission import (
    ModeloDraftStatus,
    ModeloFinding,
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionEngine,
    SubmissionError,
    SubmissionRepository,
    SubmissionStatus,
    make_submission_id,
)
from ......tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture(autouse=True)
def _secure_database(tmp_path: Path) -> Iterator[None]:
    """Run historical-record tests against a real active profile runtime."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="submission-export-test"):
        yield


class _Draft(BaseModel):
    """Frozen Protocol-conforming test double for ``ModeloDraftLike``.

    Structural conformance only — ``ModeloDraftLike`` declares read-only
    properties, so a frozen pydantic model satisfies it without
    inheritance.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    draft_id: str = "draft-ut"
    modelo: str = "130"
    period: Period = Field(default_factory=lambda: Period.from_year_and_code(2026, "1T"))
    profile_tax_id: str = "X1234567L"
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO
    values: dict[str, str] = Field(default_factory=dict)
    findings: tuple[ModeloFinding, ...] = ()


class _OpenDeadlines:
    """Deadline checker test double that always reports the filing window as open."""

    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        """Return ``True`` for every (modelo, period, today) tuple."""
        return True


class _OkAuthProvider:
    """Auth provider test double that reports a healthy CERTIFICATE provider."""

    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        """Return a synthetic :class:`AuthProviderDescription` for the test."""
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
    """Construct a :class:`SubmissionEngine` rooted at ``tmp_path``."""
    return SubmissionEngine(
        auth_provider=_OkAuthProvider(),
        deadline_checker=_OpenDeadlines(),
        settings=Settings(
            aeat_submissions_dir=tmp_path / "submissions",
            aeat_submission_browser_trace_dir=tmp_path / "traces",
        ),
    )


def _historical_filing(submission_id: str = "sub-1", modelo: str = "130") -> ModeloPresentado:
    """Build a synthetic :class:`ModeloPresentado` for historical-records tests."""
    now = datetime.now(UTC)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id="draft-1",
        modelo=modelo,
        period=Period.from_year_and_code(2026, "1T"),
        profile_tax_id="X1234567L",
        status=SubmissionStatus.PENDIENTE_DE_PRESENTAR,
        submitted_at=now,
        attempts=(
            SubmissionAttempt(
                attempt_id="attempt-1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.PENDIENTE_DE_PRESENTAR,
            ),
        ),
    )


class TestPreflightOnly:
    """The engine still runs preflight checks without any transport wired in."""

    def test_preflight_still_runs_without_transport(self, tmp_path: Path) -> None:
        """Assert preflight executes against a read-only engine."""
        engine = _build_engine(tmp_path)
        assert hasattr(engine, "preflight")
        result = engine.preflight(_Draft(), today=date(2026, 4, 10))
        assert result is None


class TestTransportRefusal:
    """The engine never exposes a submit method or accepts a browser session."""

    def test_transport_methods_are_not_exposed(self, tmp_path: Path) -> None:
        """Assert ``submit_draft`` / ``submit_amendment`` are absent and no submissions dir is created."""
        engine = _build_engine(tmp_path)
        assert not hasattr(engine, "submit_draft")
        assert not hasattr(engine, "submit_amendment")
        assert not (tmp_path / "submissions").exists()


class TestHistoricalRecords:
    """Historical-records loader behaviour for previously-persisted filings."""

    def test_load_submission_roundtrip_for_existing_local_record(self, tmp_path: Path) -> None:
        """Assert ``load_submission`` round-trips a previously persisted encrypted record."""
        engine = _build_engine(tmp_path)
        filing = _historical_filing(submission_id=make_submission_id("draft-1", 1))
        SubmissionRepository().save(filing)
        assert engine.load_submission(filing.submission_id) == filing

    def test_load_submission_rejects_traversal_id(self, tmp_path: Path) -> None:
        """Assert ``load_submission`` rejects a path-traversal submission id."""
        engine = _build_engine(tmp_path)
        with pytest.raises(SubmissionError, match="path separators"):
            engine.load_submission("../escape")

    def test_list_filters_by_modelo(self, tmp_path: Path) -> None:
        """Assert ``list_submissions(modelo=...)`` filters by modelo and returns the empty tuple on a miss."""
        engine = _build_engine(tmp_path)
        first = _historical_filing(submission_id="sub-1", modelo="130")
        second = _historical_filing(submission_id="sub-2", modelo="303")
        repository = SubmissionRepository()
        for filing in (first, second):
            repository.save(filing)
        assert engine.list_submissions(modelo="130") == (first,)
        assert engine.list_submissions(modelo="999") == ()
