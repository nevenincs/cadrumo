"""Shared helpers for the ``aeat submission`` CLI sub-app."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import cast

import typer
from pydantic import ValidationError

from ...config import Settings, load_settings
from ...filing import FilingDraft, FilingDraftError, refresh_review_status
from ...filing.runtime import build_runtime_schema_provider
from ...submission import (
    AuthProviderDescription,
    AuthProviderKind,
    CasillaInputKind,
    CasillaRecord,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    Justificante,
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
    """``DraftLoader`` implementation for persisted filing drafts.

    The primary path loads the real :class:`aeat.filing.FilingDraft`
    JSON emitted by ``aeat filing build`` / ``aeat review`` and
    refreshes approval staleness before returning. A narrow fallback
    remains for older lightweight CLI fixtures that still serialize
    ``values`` as a plain mapping.
    """

    def load(self, draft_path: Path) -> FilingDraftLike:
        payload_text = draft_path.read_text(encoding="utf-8")
        filing_draft = _load_persisted_filing_draft(draft_path, payload_text=payload_text)
        if filing_draft is not None:
            return cast(FilingDraftLike, filing_draft)
        raw = json.loads(payload_text)
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


class _CliAuthProvider:
    """Deterministic auth-provider probe used by the CLI.

    Reports a ready certificate-backed provider description so dry-run
    and preflight can exercise the real submission engine flow.
    """

    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(
            kind=self.kind,
            label="CLI certificate provider",
            configured=True,
            available=True,
            identity_nif="12345678Z",
            subject="CN=cli-provider",
            expires_on=date(2099, 12, 31),
            health_summary="OK:26800",
        )


class _CliPortalCatalogue:
    """Deterministic :class:`PortalCatalogue` used by the CLI."""

    def portal_for(self, modelo: str) -> Portal:
        return Portal(
            modelo=modelo,
            presentation_url=f"https://sede.agenciatributaria.gob.es/modelo-{modelo}",
        )


class _CliCasillaCatalogue:
    """Deterministic :class:`CasillaCatalogue` used by the CLI."""

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


class _CliJustificanteParser:
    """Deterministic :class:`JustificanteParser` used by the CLI."""

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
    """Construct a :class:`SubmissionEngine` with in-process CLI adapters.

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
    # The submission engine is dry-run only. The CLI never exposes a
    # live AEAT write path.
    return SubmissionEngine(
        browser_session_factory=_NullSession,
        auth_provider=_CliAuthProvider(),
        portal_catalogue=_CliPortalCatalogue(),
        draft_loader=_CliDraftLoader(),
        deadline_checker=_OpenDeadlineChecker(),
        casilla_catalogue=_CliCasillaCatalogue(),
        justificante_parser=_CliJustificanteParser(),
        submitters=submitters,
        settings=cfg,
    )


def load_draft(path: Path) -> FilingDraftLike:
    """Load a persisted filing draft JSON from disk.

    Real filing drafts are refreshed through
    :func:`aeat.filing.refresh_review_status` before being returned so
    submission preflight never trusts stale on-disk approval state.
    """
    return _CliDraftLoader().load(path)


def resolve_draft_path(draft_ref: str) -> Path:
    """Resolve ``draft_ref`` as either a draft path or a persisted draft id."""

    candidate = Path(draft_ref)
    if candidate.exists():
        return candidate
    if candidate.suffix == ".json" or candidate.parent != Path("."):
        raise typer.BadParameter(f"draft file not found: {candidate}")
    drafts_dir = load_settings().aeat_drafts_dir.resolve()
    matches = sorted(path for path in drafts_dir.glob(f"*_{draft_ref}.json") if path.is_file())
    if not matches:
        raise typer.BadParameter(f"no persisted draft found for draft_ref={draft_ref!r}")
    if len(matches) > 1:
        joined = ", ".join(str(path) for path in matches)
        raise typer.BadParameter(f"draft_ref={draft_ref!r} matched multiple draft files: {joined}")
    return matches[0]


def _load_persisted_filing_draft(
    draft_path: Path,
    *,
    payload_text: str,
) -> FilingDraft | None:
    try:
        draft = FilingDraft.model_validate_json(payload_text)
    except (FilingDraftError, ValidationError):
        return None
    refreshed = refresh_review_status(
        draft,
        schema_provider=build_runtime_schema_provider(),
    )
    if refreshed != draft:
        draft_path.write_text(refreshed.model_dump_json(indent=2), encoding="utf-8")
    return refreshed
