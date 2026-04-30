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
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    SubmissionEngine,
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
        filing_draft = _load_persisted_filing_draft(draft_path)
        if filing_draft is not None:
            return cast(FilingDraftLike, filing_draft)
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


class _CliAuthProvider:
    """Deterministic auth-provider probe used by the CLI.

    Reports a ready certificate-backed provider description so
    preflight can exercise the real submission engine gates.
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


def build_engine(settings: Settings | None = None) -> SubmissionEngine:
    """Construct a read-only :class:`SubmissionEngine` for CLI preflight.

    Args:
        settings: Optional settings override (used by tests).

    Returns:
        A :class:`SubmissionEngine` that can run preflight and read
        historical local records. Transport calls always fail closed.
    """
    cfg = settings or load_settings()
    return SubmissionEngine(
        auth_provider=_CliAuthProvider(),
        deadline_checker=_OpenDeadlineChecker(),
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
    """Resolve ``draft_ref`` as either a draft envelope path or a draft id."""
    candidate = Path(draft_ref)
    if candidate.exists():
        return candidate
    if candidate.suffix == ".json" or candidate.parent != Path("."):
        raise typer.BadParameter(f"draft file not found: {candidate}")
    drafts_dir = load_settings().aeat_drafts_dir.resolve()
    envelope_path = drafts_dir / f"{draft_ref}.envelope.json"
    if envelope_path.exists():
        return envelope_path
    raise typer.BadParameter(f"no persisted draft found for draft_ref={draft_ref!r}")


def _load_persisted_filing_draft(draft_path: Path) -> FilingDraft | None:
    """Load a ciphertext envelope through :class:`FilingDraftRepository`.

    Returns the refreshed draft (re-persisting through the repository
    when the refresh produced a new state) or ``None`` when the path is
    not an envelope file or the envelope cannot be deserialised.
    """
    from ...filing._repository import FilingDraftRepository

    if not draft_path.name.endswith(".envelope.json"):
        return None
    repository = FilingDraftRepository(store_dir=draft_path.parent)
    draft_id = draft_path.name[: -len(".envelope.json")]
    try:
        draft = repository.load(draft_id)
    except (FilingDraftError, ValidationError):
        return None
    if draft is None:
        return None
    refreshed = refresh_review_status(
        draft,
        schema_provider=build_runtime_schema_provider(),
    )
    if refreshed != draft:
        repository.save(refreshed)
    return refreshed
