"""Unit tests for :class:`aeat.submission.SubmissionEngine`."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ..config import Settings
from ..filing import (
    AmendmentKind,
    CasillaChange,
    FilingAmendment,
    approve_draft,
    build_draft,
)
from ..filing.testing import SyntheticProfile, default_schema_provider
from ..financial.transactions import TransactionCatalogue
from . import (
    AeatLiveSubmitNotEnabledError,
    AeatLiveTransportUnavailableError,
    AeatPytestLiveWriteRefusedError,
    AmendmentSubmissionResult,
    AuthProviderDescription,
    AuthProviderKind,
    CasillaInputKind,
    CasillaRecord,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    Justificante,
    Portal,
    SubmissionAttempt,
    SubmissionEngine,
    SubmissionError,
    SubmissionStatus,
    Submitter,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]

# ------------------------------ test doubles ---------------------------------


@dataclass
class _Draft(FilingDraftLike):
    draft_id: str = "draft-ut"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.APPROVED
    values: dict[str, str] = field(default_factory=dict)
    findings: tuple[FilingFinding, ...] = ()


class _Session:
    async def navigate(self, url: str) -> None:
        pass

    async def fill(self, selector: str, value: str) -> None:
        pass

    async def click(self, selector: str) -> None:
        pass

    async def screenshot(self, path: Path) -> None:
        pass

    async def trace_start(self, name: str) -> None:
        pass

    async def trace_stop(self, path: Path) -> None:
        pass

    async def snapshot_form_state(self, path: Path) -> None:
        pass


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


class _PortalCat:
    def portal_for(self, modelo: str) -> Portal:
        return Portal(modelo=modelo, presentation_url=f"https://sede.example.test/{modelo}")


class _Casillas:
    def casillas_for_modelo(self, modelo: str) -> tuple[CasillaRecord, ...]:
        return (
            CasillaRecord(
                id="01",
                label={"en": "x", "es": "x", "hu": "x"},
                input_kind=CasillaInputKind.NUMBER,
            ),
        )

    def get(self, casilla_id: str) -> CasillaRecord:
        return self.casillas_for_modelo("130")[0]


class _Parser:
    def parse(self, raw_bytes: bytes) -> Justificante:
        return Justificante(csv="CSV-1", pdf_path=Path("var/j.pdf"))


class _Drafts:
    def load(self, draft_path: Path) -> Any:
        raise NotImplementedError


class _RecordingSubmitter(Submitter):
    """Submitter test double that records which path was called."""

    def __init__(self) -> None:
        self.dry_run_calls = 0
        self.submit_calls = 0
        self.last_kwargs: dict[str, Any] = {}

    @property
    def modelo(self) -> str:
        return "130"

    async def dry_run(self, **kwargs: Any) -> SubmissionAttempt:
        self.dry_run_calls += 1
        self.last_kwargs = kwargs
        now = datetime.now(UTC)
        return SubmissionAttempt(
            attempt_id="dry-1",
            started_at=now,
            ended_at=now,
            status=SubmissionStatus.PENDING,
        )

    async def submit(self, **kwargs: Any) -> tuple[SubmissionAttempt, Justificante | None]:
        self.submit_calls += 1
        self.last_kwargs = kwargs
        now = datetime.now(UTC)
        attempt = SubmissionAttempt(
            attempt_id="live-1",
            started_at=now,
            ended_at=now,
            status=SubmissionStatus.SUBMITTED,
        )
        return attempt, Justificante(csv="CSV-99", pdf_path=Path("var/j.pdf"))


def _build_engine(
    tmp_path: Path,
    *,
    live_submit_enabled: bool = False,
    live_transport_supported: bool = True,
) -> tuple[SubmissionEngine, _RecordingSubmitter]:
    settings = Settings(
        aeat_submissions_dir=tmp_path / "submissions",
        aeat_submission_browser_trace_dir=tmp_path / "traces",
        aeat_live_submit_enabled=live_submit_enabled,
    )
    submitter = _RecordingSubmitter()
    engine = SubmissionEngine(
        browser_session_factory=_Session,
        auth_provider=_OkAuthProvider(),
        portal_catalogue=_PortalCat(),
        draft_loader=_Drafts(),
        deadline_checker=_OpenDeadlines(),
        casilla_catalogue=_Casillas(),
        justificante_parser=_Parser(),
        submitters={"130": submitter},
        settings=settings,
        live_transport_supported=live_transport_supported,
    )
    return engine, submitter


def _build_amendment() -> FilingAmendment:
    amended_draft = build_draft(
        modelo="130",
        period="2024Q1",
        profile=SyntheticProfile(
            tax_id="X1234567L",
            display_name="Amendment subject",
            applicable_modelos=("130",),
        ),
        inputs={
            "01": 13000,
            "02": 3500,
            "05": 400,
            "06": 0,
        },
        schema_provider=default_schema_provider(),
    )
    approved_amended_draft = approve_draft(
        amended_draft,
        approved_by="kent",
        schema_provider=default_schema_provider(),
        transaction_catalogue=TransactionCatalogue(),
    )
    return FilingAmendment(
        amendment_id="amd-1",
        submission_id="sub-1",
        original_csv="CSV-ORIGINAL",
        original_model="130",
        original_period="2024Q1",
        amendment_kind=AmendmentKind.COMPLEMENTARIA,
        delta=(
            CasillaChange(
                casilla_code="01",
                old_value=None,
                new_value=Decimal("13000"),
                reason="Test amendment",
            ),
        ),
        amended_draft=approved_amended_draft,
        created_at=datetime.now(UTC),
    )


class TestSubmitDraftDryRun:
    def test_explicit_dry_run(self, tmp_path: Path) -> None:
        engine, submitter = _build_engine(tmp_path)
        filing = asyncio.run(engine.submit_draft(_Draft(), dry_run=True))
        assert submitter.dry_run_calls == 1
        assert submitter.submit_calls == 0
        assert filing.status is SubmissionStatus.PENDING
        # Persisted through the wave-4 SubmissionRepository — envelope
        # filename, AUDIT-classification gate.
        persisted = tmp_path / "submissions" / f"{filing.submission_id}.envelope.json"
        assert persisted.exists()

    def test_dry_run_roundtrip(self, tmp_path: Path) -> None:
        engine, _ = _build_engine(tmp_path)
        filing = asyncio.run(engine.submit_draft(_Draft(), dry_run=True))
        restored = engine.load_submission(filing.submission_id)
        assert restored == filing

    def test_load_submission_rejects_traversal_id(self, tmp_path: Path) -> None:
        engine, _ = _build_engine(tmp_path)
        with pytest.raises(SubmissionError, match="simple filename token"):
            engine.load_submission("../escape")


class TestSubmitDraftLiveGating:
    def test_live_refused_when_live_submit_gate_off(self, tmp_path: Path) -> None:
        engine, submitter = _build_engine(tmp_path)
        with pytest.raises(AeatLiveSubmitNotEnabledError, match="AEAT_LIVE_SUBMIT_ENABLED"):
            asyncio.run(engine.submit_draft(_Draft(), dry_run=False))
        assert submitter.submit_calls == 0

    def test_live_refused_under_pytest_even_with_env_open(self, tmp_path: Path) -> None:
        engine, submitter = _build_engine(
            tmp_path,
            live_submit_enabled=True,
        )
        with pytest.raises(AeatPytestLiveWriteRefusedError, match="pytest"):
            asyncio.run(engine.submit_draft(_Draft(), dry_run=False))
        assert submitter.submit_calls == 0

    def test_live_refused_when_transport_is_stubbed(self, tmp_path: Path) -> None:
        engine, submitter = _build_engine(
            tmp_path,
            live_submit_enabled=True,
            live_transport_supported=False,
        )
        with pytest.raises(AeatLiveTransportUnavailableError, match="stubbed"):
            asyncio.run(engine.submit_draft(_Draft(), dry_run=False))
        assert submitter.submit_calls == 0

    def test_default_engine_construction_is_safe_against_live(self, tmp_path: Path) -> None:
        """Default ``SubmissionEngine(...)`` is inert against live writes.

        Regression guard for the 2026-04-18 ADR: the default of
        ``live_transport_supported`` was flipped from True to False so
        that callers who omit the flag cannot accidentally reach the
        per-modelo ``submit()`` transport. ``live_submit_enabled=True``
        in Settings is intentionally on here to prove that even with
        the env gate flipped open the default-constructed engine still
        refuses.
        """
        settings = Settings(
            aeat_submissions_dir=tmp_path / "submissions",
            aeat_submission_browser_trace_dir=tmp_path / "traces",
            aeat_live_submit_enabled=True,
        )
        submitter = _RecordingSubmitter()
        engine = SubmissionEngine(
            browser_session_factory=_Session,
            auth_provider=_OkAuthProvider(),
            portal_catalogue=_PortalCat(),
            draft_loader=_Drafts(),
            deadline_checker=_OpenDeadlines(),
            casilla_catalogue=_Casillas(),
            justificante_parser=_Parser(),
            submitters={"130": submitter},
            settings=settings,
            # NOTE: live_transport_supported intentionally omitted.
        )
        assert engine.live_transport_supported is False
        with pytest.raises(AeatLiveTransportUnavailableError, match="stubbed"):
            asyncio.run(engine.submit_draft(_Draft(), dry_run=False))
        assert submitter.submit_calls == 0


class TestListSubmissions:
    def test_filter_by_modelo(self, tmp_path: Path) -> None:
        engine, _ = _build_engine(tmp_path)
        asyncio.run(engine.submit_draft(_Draft(), dry_run=True))
        all_ = engine.list_submissions()
        assert len(all_) == 1
        assert engine.list_submissions(modelo="130") == all_
        assert engine.list_submissions(modelo="303") == ()


class TestSubmitAmendment:
    def test_defaults_to_dry_run_and_persists_result(self, tmp_path: Path) -> None:
        engine, submitter = _build_engine(tmp_path)
        result = asyncio.run(engine.submit_amendment(_build_amendment(), dry_run=True))
        assert isinstance(result, AmendmentSubmissionResult)
        assert result.dry_run is True
        assert result.filing.status is SubmissionStatus.PENDING
        assert submitter.dry_run_calls == 1
        assert submitter.last_kwargs["amendment_kind"] == "complementaria"
        assert submitter.last_kwargs["original_csv"] == "CSV-ORIGINAL"
        persisted = tmp_path / "submissions" / "amendment-results" / "amd-1.envelope.json"
        assert persisted.exists()

    def test_submit_amendment_rejects_traversal_id(self, tmp_path: Path) -> None:
        engine, _ = _build_engine(tmp_path)
        amendment = _build_amendment().model_copy(update={"amendment_id": "../escape"})
        with pytest.raises(SubmissionError, match="simple filename token"):
            asyncio.run(engine.submit_amendment(amendment, dry_run=True))
