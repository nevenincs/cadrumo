"""Sync-run reconciliation stage wiring (#239, Phase 5).

Connects the Phase-3 :func:`aeat.filing.reconciliation.reconcile`
comparator into the ``aeat sync run`` pipeline. The stage iterates every
local :class:`aeat.filing.FilingDraft` on disk, skips everything outside
:attr:`aeat.filing.FilingDraftStatus.APPROVED` with an INFO-level log,
and reconciles each surviving draft against AEAT through a single
:class:`aeat.remote.RemoteFilingFetcher`. The fetcher is constructed
once per ``aeat sync run`` invocation so one :class:`aeat.auth.AeatSession`
backs every ``(modelo, period)`` pass; the stage itself never builds a
session or an authenticator — it consumes whatever fetcher the caller
threads through, matching the Protocol-stub strategy the accepted
``aeat-verify`` ADR locks.

The stage is read-only by construction: no Typer option, no CLI
argument, no function in this module mutates AEAT state. The Layer-3
grep guard at :mod:`aeat.cli.sync.test_no_write_surface` walks the two
Phase-5 source files (this module plus ``test_reconcile_stage.py``) and
rejects any drift; sibling ``sync run`` surfaces (``list``, ``show``,
``resolve``) are deliberately out of the guard's scope because they do
not share Phase-5 authorship and the sync-run orchestration already
runs through the audited :mod:`aeat.submission` engine on every write
path.

:class:`ReconcileStageSummary` is the structured return type; the
Kent-facing rendering happens in :func:`emit_reconcile_summary`, which
follows the existing Rich-console pattern already used by
``aeat sync list-divergences``. ``NOT_YET_FOUND`` surfaces through a
WARNING-level log and a prominent marker (an upper-cased label plus a
bullet pointer) so the end-of-run summary catches Kent's attention on
the "AEAT has not ingested your filing yet" path without burying the
marker in the verbose per-step stream.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.table import Table

from ...filing import FilingDraft, FilingDraftError, FilingDraftStatus
from ...filing.reconciliation import (
    FilingReconciliationDivergenceRecord,
    ReconciliationReport,
    ReconciliationStatus,
    reconcile,
    reconciliation_records,
)
from ...logging import get_logger
from ...remote import RemoteFiling, RemoteFilingFetcher

_logger = get_logger(__name__)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_NOT_YET_FOUND_MARKER: Final[str] = "NOT_YET_FOUND"
"""Upper-cased marker emitted in the human summary for missing filings.

Phase 5.3 mandates the marker is prominent in the end-of-run summary so
Kent sees which drafts AEAT has not ingested without parsing the
verbose per-step log stream.
"""

_DIVERGENT_MARKER: Final[str] = "DIVERGENT"
"""Upper-cased marker for casilla-level value divergences."""

_MATCH_MARKER: Final[str] = "MATCH"
"""Marker emitted for clean reconciliations; kept terse on purpose."""


class ReconcileStageSummary(BaseModel):
    """Structured summary of one reconcile-stage pass.

    Attributes:
        total_considered: Count of drafts the stage read off disk. Equal
            to ``match_count + divergent_count + not_yet_found_count +
            skipped_count``.
        skipped_count: Drafts skipped because their status is not
            :attr:`aeat.filing.FilingDraftStatus.APPROVED`.
        match_count: Reports whose :attr:`ReconciliationStatus.MATCH`
            verdict means Kent and AEAT agree.
        divergent_count: Reports whose
            :attr:`ReconciliationStatus.DIVERGENT` verdict means at
            least one non-rounding divergence requires Kent's attention.
        not_yet_found_count: Reports whose
            :attr:`ReconciliationStatus.NOT_YET_FOUND` verdict means
            AEAT has no record of the expected ``(modelo, period)``.
        not_yet_found_refs: Immutable tuple of
            ``(modelo, period, draft_id)`` triples identifying every
            :attr:`ReconciliationStatus.NOT_YET_FOUND` draft so the
            summary emitter can name them explicitly.
        persisted_record_ids: Immutable tuple of record ids the stage
            persisted to the divergence sink. One entry per non-rounding
            :class:`FilingReconciliationDivergenceRecord`.
    """

    model_config = _STRICT_FROZEN

    total_considered: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    match_count: int = Field(ge=0)
    divergent_count: int = Field(ge=0)
    not_yet_found_count: int = Field(ge=0)
    not_yet_found_refs: tuple[tuple[str, str, str], ...] = Field(default_factory=tuple)
    persisted_record_ids: tuple[str, ...] = Field(default_factory=tuple)


@runtime_checkable
class ReconciliationSink(Protocol):
    """Persistence contract for reconciliation divergence records.

    Mirrors the narrow surface of
    :class:`aeat.sync.DivergenceRecordRepository` but typed on the
    parallel :class:`FilingReconciliationDivergenceRecord` shape forked
    in Phase 3. Accepting the two record families on a single sink would
    silently widen the closed
    :data:`aeat.sync._divergence.DivergencePayload` union; the plan's
    fork-rationale paragraph and the non-negotiable constraint against
    modifying :mod:`aeat.sync._divergence` both govern this split.

    Only :meth:`save` is required on the Phase-5 path; a production
    implementation may extend the Protocol with the same
    ``list`` / ``load`` / ``update_resolution`` methods the schema-level
    sink exposes, but the Phase-5 integration never reads records back.
    """

    def save(self, record: FilingReconciliationDivergenceRecord) -> None:
        """Persist one :class:`FilingReconciliationDivergenceRecord`."""


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time (injection seam for tests)."""
    return datetime.now(tz=UTC)


def _iter_draft_paths(drafts_dir: Path) -> Iterable[Path]:
    """Yield every persisted draft JSON path in declaration order.

    Mirrors the loader used by :mod:`aeat.cli.filing._reconcile` so the
    stage reads the same corpus the Phase-4 CLI reads. The stage never
    mutates a draft; the file system is touched read-only.
    """
    if not drafts_dir.exists():
        return ()
    return sorted(drafts_dir.glob("*.json"))


def _load_draft(path: Path) -> FilingDraft | None:
    """Read one draft JSON file off disk or return ``None`` on malformed input.

    Malformed drafts are logged at WARNING level and dropped — the
    stage never aborts a full sync-run pass because one draft on disk
    is corrupt, and a loud warning surfaces the problem to Kent.
    """
    try:
        return FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, FilingDraftError) as exc:
        _logger.warning("sync-run reconcile: skipping malformed draft at %s: %s", path, exc)
        return None


def iter_approved_drafts(drafts_dir: Path) -> Iterator[FilingDraft]:
    """Yield every :attr:`FilingDraftStatus.APPROVED` draft on disk.

    Non-APPROVED drafts are skipped with an INFO-level log per the
    Phase-5 plan gate. Malformed drafts are skipped with a WARNING.

    Args:
        drafts_dir: Directory the :class:`aeat.filing.FilingDraft` JSON
            corpus lives in. The caller resolves this from
            ``Settings.aeat_drafts_dir`` (production) or a temporary
            directory (unit suite).

    Yields:
        Each :class:`aeat.filing.FilingDraft` whose status matches the
        APPROVED gate, in file-name order (stable across runs).
    """
    for path in _iter_draft_paths(drafts_dir):
        draft = _load_draft(path)
        if draft is None:
            continue
        if draft.status is not FilingDraftStatus.APPROVED:
            _logger.info(
                "sync-run reconcile: skipping draft %s (modelo=%s period=%s status=%s is not APPROVED)",
                draft.draft_id,
                draft.modelo,
                draft.period,
                draft.status.value,
            )
            continue
        yield draft


async def _fetch_latest_remote_filing(
    *,
    fetcher: RemoteFilingFetcher,
    draft: FilingDraft,
) -> RemoteFiling | None:
    """Pick the latest-by-``submitted_at`` AEAT filing for ``draft``.

    The comparator takes a single :class:`aeat.remote.RemoteFiling` or
    ``None``; reducing the multi-filing chain (original +
    complementarias) to the newest anchor lives at this caller boundary
    so the Phase-3 comparator stays pure. Returning ``None`` means AEAT
    has no record of the ``(modelo, period)`` pair, which feeds the
    :attr:`ReconciliationStatus.NOT_YET_FOUND` branch downstream.
    """
    filings = await fetcher.fetch_filing_detail(draft.modelo, draft.period)
    if not filings:
        return None
    ordered = sorted(filings, key=lambda filing: filing.submitted_at, reverse=True)
    return ordered[0]


async def run_reconcile_stage(
    *,
    drafts_dir: Path,
    fetcher: RemoteFilingFetcher,
    sink: ReconciliationSink,
    now: Callable[[], datetime] = _utcnow,
) -> tuple[ReconcileStageSummary, tuple[ReconciliationReport, ...]]:
    """Execute the reconcile stage against every APPROVED draft on disk.

    The single ``fetcher`` seam is the session-reuse primitive: callers
    construct the fetcher from one :class:`aeat.auth.AeatSession` and
    thread it through so every ``(modelo, period)`` reconciliation
    shares the same live AEAT connection. The 18-minute
    :data:`aeat.auth.AEAT_SESSION_IDLE_TTL` comfortably covers a
    multi-modelo pass.

    :attr:`ReconciliationStatus.MATCH` reports log at DEBUG and do not
    touch the sink. :attr:`ReconciliationStatus.DIVERGENT` and
    :attr:`ReconciliationStatus.NOT_YET_FOUND` reports log at WARNING
    and persist one :class:`FilingReconciliationDivergenceRecord` per
    non-rounding delta through the :class:`ReconciliationSink` Protocol.

    Args:
        drafts_dir: Directory holding the local filing drafts.
        fetcher: One :class:`aeat.remote.RemoteFilingFetcher` backed by
            a single :class:`aeat.auth.AeatSession` for the pass.
        sink: Persistence adapter for the reconciliation divergence
            records.
        now: Injection seam for the wall-clock timestamp used on every
            :class:`aeat.filing.reconciliation.ReconciliationReport`.
            Unit tests hand a frozen callable here.

    Returns:
        A ``(summary, reports)`` tuple: the structured
        :class:`ReconcileStageSummary` and the ordered tuple of
        :class:`aeat.filing.reconciliation.ReconciliationReport` the
        stage produced (in APPROVED-draft iteration order).
    """
    considered = 0
    skipped = 0
    matches = 0
    divergents = 0
    not_yet_found = 0
    not_yet_found_refs: list[tuple[str, str, str]] = []
    persisted_ids: list[str] = []
    reports: list[ReconciliationReport] = []

    approved: list[FilingDraft] = list(iter_approved_drafts(drafts_dir))
    # Count every draft on disk (APPROVED + skipped) for the summary.
    for path in _iter_draft_paths(drafts_dir):
        draft = _load_draft(path)
        if draft is None:
            continue
        considered += 1
        if draft.status is not FilingDraftStatus.APPROVED:
            skipped += 1

    for draft in approved:
        remote = await _fetch_latest_remote_filing(fetcher=fetcher, draft=draft)
        report = reconcile(draft, remote, now=now)
        reports.append(report)

        if report.status is ReconciliationStatus.MATCH:
            matches += 1
            _logger.debug(
                "sync-run reconcile: MATCH for draft %s (modelo=%s period=%s)",
                draft.draft_id,
                draft.modelo,
                draft.period,
            )
            continue

        if report.status is ReconciliationStatus.DIVERGENT:
            divergents += 1
            _logger.warning(
                "sync-run reconcile: DIVERGENT for draft %s (modelo=%s period=%s, %d delta(s))",
                draft.draft_id,
                draft.modelo,
                draft.period,
                len(report.casilla_deltas),
            )
        elif report.status is ReconciliationStatus.NOT_YET_FOUND:
            not_yet_found += 1
            not_yet_found_refs.append((draft.modelo, draft.period, draft.draft_id))
            _logger.warning(
                "sync-run reconcile: %s for draft %s (modelo=%s period=%s) — AEAT has no record yet",
                _NOT_YET_FOUND_MARKER,
                draft.draft_id,
                draft.modelo,
                draft.period,
            )

        for record in reconciliation_records(report):
            sink.save(record)
            persisted_ids.append(record.record_id)

    summary = ReconcileStageSummary(
        total_considered=considered,
        skipped_count=skipped,
        match_count=matches,
        divergent_count=divergents,
        not_yet_found_count=not_yet_found,
        not_yet_found_refs=tuple(not_yet_found_refs),
        persisted_record_ids=tuple(persisted_ids),
    )
    return summary, tuple(reports)


def emit_reconcile_summary(
    summary: ReconcileStageSummary,
    *,
    console: Console,
) -> None:
    """Render a :class:`ReconcileStageSummary` for the Kent-facing run summary.

    ``NOT_YET_FOUND`` refs surface with a leading upper-cased marker
    ahead of the numeric totals so Kent spots them immediately. The
    renderer matches the Rich-table convention already used by
    ``aeat sync list-divergences``; the emitter is pure output and does
    not touch the divergence sink or the fetcher.

    Args:
        summary: Structured stage summary returned by
            :func:`run_reconcile_stage`.
        console: :class:`rich.console.Console` instance to write into.
            The sync-run CLI passes its own console so output aligns
            with the rest of the run's human-facing rendering.
    """
    header = Table(title="reconcile stage", header_style="bold")
    header.add_column("metric", style="cyan")
    header.add_column("count", justify="right")
    header.add_row("considered", str(summary.total_considered))
    header.add_row("skipped (non-APPROVED)", str(summary.skipped_count))
    header.add_row(_MATCH_MARKER.lower(), str(summary.match_count))
    header.add_row(_DIVERGENT_MARKER.lower(), str(summary.divergent_count))
    header.add_row(_NOT_YET_FOUND_MARKER.lower(), str(summary.not_yet_found_count))
    console.print(header)

    if summary.not_yet_found_count:
        console.print(
            f"[bold yellow]{_NOT_YET_FOUND_MARKER}[/bold yellow]: "
            f"{summary.not_yet_found_count} draft(s) with no AEAT record yet",
        )
        for modelo, period, draft_id in summary.not_yet_found_refs:
            console.print(
                f"  [yellow]*[/yellow] modelo={modelo} period={period} draft_id={draft_id}",
            )

    if summary.divergent_count:
        console.print(
            f"[bold red]{_DIVERGENT_MARKER}[/bold red]: {summary.divergent_count} draft(s) diverge from AEAT",
        )

    if summary.persisted_record_ids:
        console.print(
            f"[dim]persisted {len(summary.persisted_record_ids)} divergence record(s)[/dim]",
        )


__all__ = [
    "ReconcileStageSummary",
    "ReconciliationSink",
    "emit_reconcile_summary",
    "iter_approved_drafts",
    "run_reconcile_stage",
]
