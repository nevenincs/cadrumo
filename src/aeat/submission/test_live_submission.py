"""Opt-in live test for the submission engine.

This module holds a single ``@pytest.mark.live`` test that performs a
DRY-RUN-ONLY engine invocation. It never enters live submission mode.
The test is skipped by default via the ``live`` marker; opt in with
``AEAT_LIVE_TESTS_ENABLED=1`` and run with the ``live`` marker selected.

Running::

    AEAT_LIVE_TESTS_ENABLED=1 uv run pytest -m live src/aeat/submission/test_live_submission.py -q
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from aeat.config import Settings
from aeat.submission import (
    CasillaRecord,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    Justificante,
    LoadedCertificate,
    Portal,
    SubmissionAttempt,
    SubmissionEngine,
    SubmissionStatus,
    Submitter,
)

pytestmark = [pytest.mark.live]


@dataclass
class _Draft(FilingDraftLike):
    draft_id: str = "live-draft"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.READY_TO_SUBMIT
    values: dict[str, str] = field(default_factory=dict)
    findings: tuple[FilingFinding, ...] = ()


class _Session:
    async def navigate(self, url: str) -> None: ...
    async def fill(self, selector: str, value: str) -> None: ...
    async def click(self, selector: str) -> None: ...
    async def screenshot(self, path: Path) -> None: ...
    async def trace_start(self, name: str) -> None: ...
    async def trace_stop(self, path: Path) -> None: ...
    async def snapshot_form_state(self, path: Path) -> None: ...


class _Deadlines:
    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        return True


class _Certs:
    def load(self) -> LoadedCertificate:
        return LoadedCertificate(
            subject="CN=Live",
            not_after=date(2099, 12, 31),
            fingerprint_sha256="a" * 64,
        )

    async def preload_into_browser_context(self, context: Any) -> None: ...


class _Portals:
    def portal_for(self, modelo: str) -> Portal:
        return Portal(modelo=modelo, presentation_url="https://sede.example.test/live")


class _Casillas:
    def casillas_for_modelo(self, modelo: str) -> tuple[CasillaRecord, ...]:
        return ()

    def get(self, casilla_id: str) -> CasillaRecord:
        raise KeyError(casilla_id)


class _Parser:
    def parse(self, raw_bytes: bytes) -> Justificante:
        return Justificante(csv="X", pdf_path=Path("x.pdf"))


class _Drafts:
    def load(self, draft_path: Path) -> Any:
        raise NotImplementedError


class _NoopSubmitter(Submitter):
    @property
    def modelo(self) -> str:
        return "130"

    async def dry_run(self, **kwargs: Any) -> SubmissionAttempt:
        now = datetime.now(UTC)
        return SubmissionAttempt(
            attempt_id="live-dry",
            started_at=now,
            ended_at=now,
            status=SubmissionStatus.PENDING,
        )

    async def submit(self, **kwargs: Any) -> tuple[SubmissionAttempt, Justificante | None]:
        raise AssertionError("live test must never call submit()")


def test_live_dry_run_only(tmp_path: Path) -> None:
    settings = Settings(
        aeat_submissions_dir=tmp_path / "submissions",
        aeat_submission_browser_trace_dir=tmp_path / "traces",
    )
    engine = SubmissionEngine(
        browser_session_factory=_Session,
        cert_backend=_Certs(),
        portal_catalogue=_Portals(),
        draft_loader=_Drafts(),
        deadline_checker=_Deadlines(),
        casilla_catalogue=_Casillas(),
        justificante_parser=_Parser(),
        submitters={"130": _NoopSubmitter()},
        settings=settings,
        audit_log_path=tmp_path / ".aeat" / "live-submit-audit.log",
    )
    filing = asyncio.run(engine.submit_draft(_Draft(), dry_run=True))
    assert filing.status is SubmissionStatus.PENDING
