"""Unit tests for the read-only :class:`cadrumo.adapters.outbound.aeat.export.SubmissionEngine`.

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

from ......adapters.persistence.profile.submission import SubmissionRepository
from ......core import AuthProviderDescription, AuthProviderKind, Period
from ......core.access_gate import AeatAccessGate, LiveSubmitForbiddenError
from ......core.config import Settings
from ......domain.submission import (
    ModeloDraftStatus,
    ModeloFinding,
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionEngine,
    SubmissionError,
    SubmissionStatus,
    make_submission_id,
)
from ......tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SUBMITTED_AT = datetime(2026, 5, 28, 12, 55, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _secure_database(tmp_path: Path) -> Iterator[None]:
    """Run historical-record tests against a real active profile runtime."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="submission-export-test"):
        yield


class _Draft(BaseModel):
    """Frozen Protocol-conforming harness record for ``ModeloDraftLike``.

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
    """Deadline checker harness that always reports the filing window as open."""

    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        """Return ``True`` for every (modelo, period, today) tuple."""
        return True


class _OkAuthProvider:
    """Auth provider harness that reports a healthy CERTIFICATE provider."""

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
        repository=SubmissionRepository(),
        settings=Settings(
            cadrumo_submissions_dir=tmp_path / "submissions",
        ),
    )


def _historical_filing(submission_id: str = "sub-1", modelo: str = "130") -> ModeloPresentado:
    """Build a synthetic :class:`ModeloPresentado` for historical-records tests."""
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id="draft-1",
        modelo=modelo,
        period=Period.from_year_and_code(2026, "1T"),
        profile_tax_id="X1234567L",
        status=SubmissionStatus.PENDIENTE_DE_PRESENTAR,
        submitted_at=_SUBMITTED_AT,
        attempts=(
            SubmissionAttempt(
                attempt_id="attempt-1",
                started_at=_SUBMITTED_AT,
                ended_at=_SUBMITTED_AT,
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

    def test_engine_public_surface_carries_no_transport_shaped_name(self, tmp_path: Path) -> None:
        """No public attribute on the engine is named like a write/transport verb.

        Closes the deferred #590 "parity" item honestly: the historical
        ``_submit_with_transport`` method this item was written against no
        longer exists anywhere in the codebase (excised by the live-write
        removal that predates this engine's current read-only shape — see
        :mod:`cadrumo.adapters.outbound.aeat.export._submitters`), so there is no
        transport code path left to compare against
        :meth:`AeatAccessGate.require_live_write`. The durable, re-checkable
        assertion is structural: the engine's entire public surface is free of
        any write-shaped name, for every current and future public attribute,
        not just the two named methods above.
        """
        engine = _build_engine(tmp_path)
        transport_shaped_tokens = ("submit", "present", "sign", "pay", "transport", "write")
        public_attrs = [name for name in dir(engine) if not name.startswith("_")]
        assert public_attrs, "engine must expose some public surface to make this assertion meaningful"
        offending = [name for name in public_attrs if any(token in name.lower() for token in transport_shaped_tokens)]
        assert offending == []

    def test_engine_has_no_write_path_that_could_disagree_with_the_access_gate(self, tmp_path: Path) -> None:
        """Cross-module agreement: no engine call can ever reach AEAT once past the gate.

        The engine has no transport method for :meth:`AeatAccessGate.require_live_write`
        to disagree with; this proves the two surfaces cannot diverge by
        proving there is nothing on the engine's public surface a caller could
        invoke to attempt a live AEAT write, while also confirming (in the same
        test) that the gate itself refuses unconditionally. Together they
        establish the invariant the original parity test intended: whichever
        path an operator takes, a live AEAT write is unreachable.
        """
        engine = _build_engine(tmp_path)
        write_shaped_methods = [
            name
            for name in dir(engine)
            if not name.startswith("_") and callable(getattr(engine, name, None)) and name not in {"preflight"}
        ]
        # preflight() is a read-only gate check, not a write; every other
        # callable public method is a pure historical-record reader.
        for name in write_shaped_methods:
            assert name in {"load_submission", "list_submissions"}, (
                f"unexpected callable public method {name!r} on SubmissionEngine; "
                "confirm it cannot reach AEAT before widening this allowlist"
            )
        with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
            AeatAccessGate(Settings()).require_live_write()


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
