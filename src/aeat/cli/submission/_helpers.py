"""Shared helpers for the ``aeat submission`` CLI sub-app."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ...config import Settings, load_settings
from ...submission import (
    CasillaInputKind,
    CasillaRecord,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    Justificante,
    LoadedCertificate,
    Modelo130Submitter,
    Portal,
    SubmissionEngine,
    Submitter,
)


@dataclass(frozen=True)
class _CliDraft(FilingDraftLike):
    """Concrete :class:`FilingDraftLike` implementation for the CLI.

    Not a mock: a real dataclass that structurally satisfies the
    :class:`FilingDraftLike` Protocol. Used only by the CLI loader as
    a stand-in until ``aeat.filing.FilingDraft`` (#39) lands.
    """

    draft_id: str
    modelo: str
    period: str
    profile_tax_id: str
    status: DraftStatus
    values: Mapping[str, str]
    findings: tuple[FilingFinding, ...] = field(default_factory=tuple)


class _CliDraftLoader:
    """``DraftLoader`` implementation for the CLI stub-draft format."""

    def load(self, draft_path: Path) -> FilingDraftLike:
        raw = json.loads(draft_path.read_text(encoding="utf-8"))
        findings = tuple(
            FilingFinding(
                severity=FilingFindingSeverity(entry["severity"]),
                message=entry["message"],
            )
            for entry in raw.get("findings", [])
        )
        return _CliDraft(
            draft_id=raw["draft_id"],
            modelo=raw["modelo"],
            period=raw["period"],
            profile_tax_id=raw["profile_tax_id"],
            status=DraftStatus(raw["status"]),
            values=dict(raw.get("values", {})),
            findings=findings,
        )


class _OpenDeadlineChecker:
    """Stub :class:`DeadlineWindowChecker` used by the CLI.

    v1 always returns ``True``; rebase swaps this for a real
    :class:`aeat.deadlines.DeadlineEngine`-backed adapter.
    """

    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        return True


class _StubCertBackend:
    """Stub :class:`CertificateBackend` used by the CLI.

    Always returns a placeholder :class:`LoadedCertificate`. Swap for
    the real backend when #8 merges.
    """

    def load(self) -> LoadedCertificate:
        return LoadedCertificate(
            subject="CN=cli-stub",
            not_after=date(2099, 12, 31),
            fingerprint_sha256="a" * 64,
        )

    async def preload_into_browser_context(self, context: Any) -> None:
        return None


class _StubPortalCatalogue:
    """Stub :class:`PortalCatalogue` used by the CLI."""

    def portal_for(self, modelo: str) -> Portal:
        return Portal(
            modelo=modelo,
            presentation_url=f"https://sede.agenciatributaria.gob.es/modelo-{modelo}",
        )


class _StubCasillaCatalogue:
    """Stub :class:`CasillaCatalogue` used by the CLI."""

    def casillas_for_modelo(self, modelo: str) -> tuple[CasillaRecord, ...]:
        return tuple(
            CasillaRecord(
                id=str(i).zfill(2),
                label={"en": f"casilla-{i}", "es": f"casilla-{i}", "hu": f"rovat-{i}"},
                input_kind=CasillaInputKind.NUMBER,
            )
            for i in range(1, 20)
        )

    def get(self, casilla_id: str) -> CasillaRecord:
        for c in self.casillas_for_modelo("130"):
            if c.id == casilla_id:
                return c
        raise KeyError(casilla_id)


class _StubJustificanteParser:
    """Stub :class:`JustificanteParser` used by the CLI."""

    def parse(self, raw_bytes: bytes) -> Justificante:
        return Justificante(csv="STUB", pdf_path=Path("justificante.pdf"))


class _NullSession:
    """Null :class:`BrowserSessionLike` used by CLI dry-runs.

    The CLI never actually launches Playwright at v1 — the
    Modelo130Submitter structure is exercised against this
    deterministic session. Production call sites override the engine's
    ``browser_session_factory`` to return a real
    :class:`aeat.browser.BrowserSession`.
    """

    async def navigate(self, url: str) -> None: ...
    async def fill(self, selector: str, value: str) -> None: ...
    async def click(self, selector: str) -> None: ...
    async def screenshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")

    async def trace_start(self, name: str) -> None: ...
    async def trace_stop(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")

    async def snapshot_form_state(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")


def build_engine(settings: Settings | None = None) -> SubmissionEngine:
    """Construct a :class:`SubmissionEngine` with in-process CLI stubs.

    Args:
        settings: Optional settings override (used by tests).

    Returns:
        A fully wired :class:`SubmissionEngine` ready to dispatch
        ``submit_draft`` calls.
    """
    cfg = settings or load_settings()
    submitters: dict[str, Submitter] = {
        "130": Modelo130Submitter(artifact_dir=cfg.aeat_submission_browser_trace_dir),
    }
    # live_transport_supported defaults to False (engine-level opt-in
    # only, see 2026-04-18-live-submit-cli-excision-adr). The CLI
    # surface never opts in.
    return SubmissionEngine(
        browser_session_factory=_NullSession,
        cert_backend=_StubCertBackend(),
        portal_catalogue=_StubPortalCatalogue(),
        draft_loader=_CliDraftLoader(),
        deadline_checker=_OpenDeadlineChecker(),
        casilla_catalogue=_StubCasillaCatalogue(),
        justificante_parser=_StubJustificanteParser(),
        submitters=submitters,
        settings=cfg,
    )


def load_draft(path: Path) -> FilingDraftLike:
    """Load a CLI-format draft JSON from disk."""
    return _CliDraftLoader().load(path)
