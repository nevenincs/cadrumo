"""Opt-in live test for the submission engine.

This module holds a single ``live_read`` test (historical - previously
``@pytest.mark.live``) that performs a DRY-RUN-ONLY engine invocation.
It never enters live submission mode. The test is skipped by default
via the ``live_read`` marker; opt in with ``AEAT_LIVE_TESTS_ENABLED=1``
and run with the ``live_read`` marker selected.

Running::

    AEAT_LIVE_TESTS_ENABLED=1 uv run pytest -m live_read src/aeat/submission/test_live_submission.py -q
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from ..config import Settings
from . import (
    AuthProviderDescription,
    AuthProviderKind,
    CasillaRecord,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    Justificante,
    Portal,
    SubmissionAttempt,
    SubmissionEngine,
    SubmissionStatus,
    Submitter,
)

pytestmark = [pytest.mark.live_read, pytest.mark.domain_submission]


@dataclass
class _Draft(FilingDraftLike):
    draft_id: str = "live-draft"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.APPROVED
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


class _AuthProvider:
    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(
            kind=self.kind,
            label="Live test certificate",
            configured=True,
            available=True,
            identity_nif="X1234567L",
            subject="CN=Live",
            expires_on=date(2099, 12, 31),
            health_summary="OK:26800",
        )


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
        raise AssertionError("live dry-run test must not parse justificantes")


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


def test_live_dry_run_only(tmp_path: Path) -> None:
    settings = Settings(
        aeat_submissions_dir=tmp_path / "submissions",
        aeat_submission_browser_trace_dir=tmp_path / "traces",
    )
    engine = SubmissionEngine(
        browser_session_factory=_Session,
        auth_provider=_AuthProvider(),
        portal_catalogue=_Portals(),
        draft_loader=_Drafts(),
        deadline_checker=_Deadlines(),
        casilla_catalogue=_Casillas(),
        justificante_parser=_Parser(),
        submitters={"130": _NoopSubmitter()},
        settings=settings,
    )
    filing = asyncio.run(engine.submit_draft(_Draft(), dry_run=True))
    assert filing.status is SubmissionStatus.PENDING
