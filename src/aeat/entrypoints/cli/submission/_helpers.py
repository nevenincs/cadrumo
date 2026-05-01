"""Shared helpers for the ``aeat submission`` CLI sub-app.

Hosts the CLI-side compatibility fixtures (draft loader, no-op deadline
checker, deterministic auth-provider probe) that let
:class:`aeat.adapters.outbound.aeat.export.SubmissionEngine` run inside
the typer entrypoints without dragging the real runtime auth and
deadline machinery into every CLI invocation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import cast

import typer
from pydantic import ValidationError

from ....adapters.outbound.aeat.export import (
    AuthProviderDescription,
    AuthProviderKind,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    SubmissionEngine,
)
from ....application.filing import FilingDraft, FilingDraftError, refresh_review_status
from ....application.filing.runtime import build_runtime_schema_provider
from ....core.config import Settings, load_settings


@dataclass(frozen=True)
class _CliDraft(FilingDraftLike):
    """Compatibility :class:`FilingDraftLike` for legacy CLI fixtures.

    Structurally satisfies the
    :class:`aeat.adapters.outbound.aeat.export.FilingDraftLike` protocol
    so the lightweight plaintext-JSON draft format the CLI tests still
    use can flow through the submission engine. Production drafts use
    :class:`aeat.application.filing.FilingDraft` directly.

    Attributes:
        draft_id: Stable identifier for the draft.
        modelo: AEAT modelo code (e.g. ``"130"``, ``"303"``).
        period: Reporting period (e.g. ``"2026Q1"``).
        profile_tax_id: NIF of the operator the draft belongs to.
        status: Current
            :class:`aeat.adapters.outbound.aeat.export.DraftStatus`.
        values: Mapping of casilla id to string value.
        findings: Tuple of
            :class:`aeat.adapters.outbound.aeat.export.FilingFinding`
            entries surfaced by validation.
    """

    draft_id: str
    modelo: str
    period: str
    profile_tax_id: str
    status: DraftStatus
    values: Mapping[str, str]
    findings: tuple[FilingFinding, ...] = field(default_factory=tuple)


class _CliDraftLoader:
    """Draft loader that prefers persisted :class:`FilingDraft` envelopes.

    The primary path loads the real
    :class:`aeat.application.filing.FilingDraft` JSON emitted by
    ``aeat filing build`` and ``aeat review``, refreshing approval
    staleness via
    :func:`aeat.application.filing.refresh_review_status` before returning.
    A narrow fallback remains for older lightweight CLI fixtures that
    serialise ``values`` as a plain mapping; that path returns a
    :class:`_CliDraft`.
    """

    def load(self, draft_path: Path) -> FilingDraftLike:
        """Load a draft from ``draft_path``.

        Args:
            draft_path: Filesystem path to either an envelope-format
                draft (``*.envelope.json``) or a legacy plaintext JSON
                fixture.

        Returns:
            A :class:`FilingDraftLike` ready for the submission engine.
        """
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
    """Always-open deadline checker used by the CLI preflight harness.

    The first version always returns ``True``; a future revision will
    swap this for a real
    :class:`aeat.domain.deadlines.DeadlineEngine`-backed adapter.
    """

    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        """Return ``True`` for every modelo, period, and date.

        Args:
            modelo: AEAT modelo code.
            period: Reporting period token.
            today: Calendar date the check is made against.

        Returns:
            Always ``True``.
        """
        return True


class _CliAuthProvider:
    """Deterministic auth-provider probe for the CLI submission engine.

    Reports a ready certificate-backed provider description so preflight
    can exercise the real submission-engine gates without touching any
    on-disk auth state.

    Attributes:
        kind: Always
            :attr:`aeat.adapters.outbound.aeat.export.AuthProviderKind.CERTIFICATE`.
    """

    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        """Return a deterministic auth-provider description.

        Returns:
            A populated
            :class:`aeat.adapters.outbound.aeat.export.AuthProviderDescription`
            announcing a configured, available certificate provider.
        """
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
    """Construct a read-only submission engine for CLI preflight.

    Args:
        settings: Optional :class:`aeat.core.config.Settings` override
            used by tests; defaults to
            :func:`aeat.core.config.load_settings` when omitted.

    Returns:
        A :class:`aeat.adapters.outbound.aeat.export.SubmissionEngine`
        that can run preflight and read historical local records.
        Transport calls always fail closed.
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
    :func:`aeat.application.filing.refresh_review_status` before being
    returned, so submission preflight never trusts stale on-disk
    approval state.

    Args:
        path: Filesystem path to the draft.

    Returns:
        A :class:`FilingDraftLike` ready for submission-engine consumption.
    """
    return _CliDraftLoader().load(path)


def resolve_draft_path(draft_ref: str) -> Path:
    """Resolve ``draft_ref`` as either a draft envelope path or a draft id.

    Args:
        draft_ref: Either an existing filesystem path or a bare draft
            id; bare ids are looked up under the configured
            :attr:`aeat.core.config.Settings.aeat_drafts_dir`.

    Returns:
        Filesystem path to the resolved envelope.

    Raises:
        typer.BadParameter: When the path does not exist and no
            envelope file matches the bare id.
    """
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

    Args:
        draft_path: Path to a draft file. Must end in ``.envelope.json``
            for the envelope path to fire.

    Returns:
        The refreshed
        :class:`aeat.application.filing.FilingDraft`, re-persisting
        through the repository when the refresh produced a new state, or
        ``None`` when ``draft_path`` is not an envelope file or the
        envelope cannot be deserialised.
    """
    from ....domain.filing import FilingDraftRepository

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
