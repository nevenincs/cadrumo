"""Unit tests for :class:`aeat.submission.Modelo130Submitter`.

Tests pass a :class:`RecordingSession` that implements
:class:`BrowserSessionLike` and records every call into a list. This
is a real Protocol implementation, not a mock.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from aeat.submission import (
    BrowserSessionLike,
    CasillaInputKind,
    CasillaRecord,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    Modelo130Submitter,
    Portal,
    SubmissionFormFillError,
    SubmissionStatus,
)

pytestmark = pytest.mark.unit


@dataclass
class _Draft(FilingDraftLike):
    draft_id: str = "draft-modelo130"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.READY_TO_SUBMIT
    values: dict[str, str] = field(default_factory=lambda: {"01": "1500.00", "03": "200.00"})
    findings: tuple[FilingFinding, ...] = ()


class _Catalogue:
    def casillas_for_modelo(self, modelo: str) -> tuple[CasillaRecord, ...]:
        return (
            CasillaRecord(
                id="01",
                label={"en": "ingresos", "es": "ingresos", "hu": "bevétel"},
                input_kind=CasillaInputKind.NUMBER,
            ),
            CasillaRecord(
                id="03",
                label={"en": "gastos", "es": "gastos", "hu": "kiadás"},
                input_kind=CasillaInputKind.NUMBER,
            ),
        )

    def get(self, casilla_id: str) -> CasillaRecord:
        for c in self.casillas_for_modelo("130"):
            if c.id == casilla_id:
                return c
        raise KeyError(casilla_id)


class RecordingSession:
    """Deterministic :class:`BrowserSessionLike` implementation for tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def navigate(self, url: str) -> None:
        self.calls.append(("navigate", (url,)))

    async def fill(self, selector: str, value: str) -> None:
        self.calls.append(("fill", (selector, value)))

    async def click(self, selector: str) -> None:
        self.calls.append(("click", (selector,)))

    async def screenshot(self, path: Path) -> None:
        self.calls.append(("screenshot", (path,)))

    async def trace_start(self, name: str) -> None:
        self.calls.append(("trace_start", (name,)))

    async def trace_stop(self, path: Path) -> None:
        self.calls.append(("trace_stop", (path,)))

    async def snapshot_form_state(self, path: Path) -> None:
        self.calls.append(("snapshot_form_state", (path,)))


def _portal() -> Portal:
    return Portal(modelo="130", presentation_url="https://sede.example.test/m130")


def test_recording_session_structurally_conforms() -> None:
    session: BrowserSessionLike = RecordingSession()
    assert isinstance(session, BrowserSessionLike)


def test_dry_run_fills_and_aborts_before_submit(tmp_path: Path) -> None:
    submitter = Modelo130Submitter(artifact_dir=tmp_path)
    session = RecordingSession()
    attempt = asyncio.run(
        submitter.dry_run(
            draft=_Draft(),
            session=session,
            casilla_catalogue=_Catalogue(),
            portal=_portal(),
        )
    )
    names = [call[0] for call in session.calls]
    assert "navigate" in names
    assert names.count("fill") == 2
    assert "snapshot_form_state" in names
    assert "click" not in names  # dry-run MUST NOT click submit
    assert "trace_start" in names
    assert "trace_stop" in names
    assert attempt.status is SubmissionStatus.PENDING


def test_submit_clicks_submit_and_records_submitted(tmp_path: Path) -> None:
    submitter = Modelo130Submitter(artifact_dir=tmp_path)
    session = RecordingSession()
    attempt, justificante = asyncio.run(
        submitter.submit(
            draft=_Draft(),
            session=session,
            casilla_catalogue=_Catalogue(),
            portal=_portal(),
        )
    )
    names = [call[0] for call in session.calls]
    assert names.count("fill") == 2
    click_calls = [c for c in session.calls if c[0] == "click"]
    assert len(click_calls) == 1
    selector = click_calls[0][1][0]
    assert isinstance(selector, str)
    assert "firmar-y-enviar" in selector
    assert attempt.status is SubmissionStatus.SUBMITTED
    assert justificante is None  # v1: parser runs outside the submitter


def test_unknown_casilla_raises(tmp_path: Path) -> None:
    submitter = Modelo130Submitter(artifact_dir=tmp_path)
    draft = _Draft(values={"99": "99.00"})
    with pytest.raises(SubmissionFormFillError, match="unknown casilla"):
        asyncio.run(
            submitter.dry_run(
                draft=draft,
                session=RecordingSession(),
                casilla_catalogue=_Catalogue(),
                portal=_portal(),
            )
        )
