"""``aeat filing reconcile`` subcommand implementation (#239, Phase 4).

Wires :func:`aeat.filing.reconciliation.reconcile` into the Kent-facing
CLI. The command is read-only by construction: no Typer option defined
here mutates AEAT state, and the parser pre-guard rejects every
English / Spanish write-verb flag (``--write``, ``--submit``,
``--enviar``, ``--presentar``, ``--firmar``, ``--commit``, ``--send``)
before Typer's command body runs. The flag is never declared as a
Typer option — declaring it would defeat the write-guard posture the
charter #116 live-write safety charter locks.

Two resolution modes are supported:

* Positional ``<draft-id>`` — load the named draft by id from the
  configured drafts directory.
* ``--last --modelo M --period P`` — pick the most recent approved
  draft matching ``(modelo, period)``.

The reconciler itself is pure. Remote data is fetched via the
:class:`aeat.remote.RemoteFilingFetcher` Protocol; tests inject a
Protocol-conforming Python class (no mocks) and production wires the
real Playwright-based fetcher in :mod:`aeat.remote.filings` — Phase 5
lands the sync-run integration that reuses one ``AeatSession`` across
a whole pass.
"""

from __future__ import annotations

import asyncio
import json as _json
import sys
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Final

import typer
from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.table import Table

from ...config import load_settings
from ...errors import AeatError
from ...filing import FilingDraft, FilingDraftError, FilingDraftStatus
from ...filing.reconciliation import (
    ReconciliationReport,
    ReconciliationStatus,
    reconcile,
)
from ...i18n import Language, Translatable, get_translation
from ...logging import get_logger
from ...remote import RemoteFiling, RemoteFilingFetcher

_console = Console()
_logger = get_logger(__name__)

_WRITE_GUARD_ISSUE: Final[str] = "#116"
"""Live-write safety charter issue referenced in the guard error."""

_FORBIDDEN_FLAGS: Final[tuple[str, ...]] = (
    "--write",
    "--submit",
    "--enviar",
    "--presentar",
    "--firmar",
    "--commit",
    "--send",
)
"""Flags refused at parser level; never declared as Typer options."""


_STATUS_TO_EXIT_CODE: Final[MappingProxyType[ReconciliationStatus, int]] = MappingProxyType(
    {
        ReconciliationStatus.MATCH: 0,
        ReconciliationStatus.DIVERGENT: 1,
        ReconciliationStatus.NOT_YET_FOUND: 2,
    }
)
"""ADR-locked exit-code table keyed on the terminal triad member."""


def reject_forbidden_flags(argv: Sequence[str]) -> None:
    """Reject any forbidden write-verb flag at pre-parser level.

    The guard scans ``argv`` for an exact occurrence of any entry in
    :data:`_FORBIDDEN_FLAGS`, including the ``--flag=value`` shape. The
    flag is refused with a :class:`typer.BadParameter` that Typer maps
    to exit-code ``2``. None of the flags are declared as Typer
    options anywhere in this module — the refusal is the only reason
    ``--write`` (and siblings) cannot be passed.

    Args:
        argv: The raw argv tail as observed by the invoked command.
            Callers typically pass :data:`sys.argv[1:]`.

    Raises:
        typer.BadParameter: When a forbidden flag is present in
            ``argv``.
    """
    for arg in argv:
        for forbidden in _FORBIDDEN_FLAGS:
            if arg == forbidden or arg.startswith(f"{forbidden}="):
                raise typer.BadParameter(
                    (
                        f"aeat filing reconcile is read-only; writes are not supported "
                        f"(refusing {forbidden!r} — refer to issue {_WRITE_GUARD_ISSUE})."
                    ),
                    param_hint=forbidden,
                )


class ReconcileCliArgs(BaseModel):
    """Normalised arguments resolved from the raw CLI invocation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    draft_id: str | None = Field(default=None)
    modelo: str | None = Field(default=None, max_length=8)
    period: str | None = Field(default=None, max_length=16)
    last: bool = False
    as_json: bool = False
    dry_run: bool = False


def _drafts_dir() -> Path:
    """Return the configured drafts directory, creating it on demand."""
    settings = load_settings()
    path = Path(settings.aeat_drafts_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _output_language() -> Language:
    """Resolve Kent's active output language; default to Spanish."""
    try:
        return Language(load_settings().aeat_output_language)
    except (KeyError, ValueError):
        _logger.warning(
            "aeat_output_language could not be resolved; defaulting to Spanish.",
        )
        return Language.ES


def _load_draft(path: Path) -> FilingDraft:
    """Read and parse one draft JSON file off disk."""
    try:
        return FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, FilingDraftError) as exc:
        raise typer.BadParameter(f"invalid draft in {path}: {exc}") from exc


def _iter_draft_paths(drafts_dir: Path) -> Iterable[Path]:
    """Yield every persisted draft JSON path in declaration order."""
    return sorted(drafts_dir.glob("*.json"))


def _resolve_draft_by_id(draft_id: str) -> FilingDraft:
    """Look up a draft by its content-addressed id or fail loudly."""
    drafts_dir = _drafts_dir()
    for path in _iter_draft_paths(drafts_dir):
        suffix = f"_{draft_id}.json"
        if path.name.endswith(suffix):
            draft = _load_draft(path)
            if draft.draft_id == draft_id:
                return draft
    raise typer.BadParameter(
        f"no draft found with id {draft_id!r} under {drafts_dir}",
    )


def _resolve_latest_approved(modelo: str, period: str) -> FilingDraft:
    """Pick the most recent APPROVED draft for ``(modelo, period)``."""
    drafts_dir = _drafts_dir()
    prefix = f"{modelo}_{period}_"
    candidates: list[FilingDraft] = []
    for path in _iter_draft_paths(drafts_dir):
        if not path.name.startswith(prefix):
            continue
        draft = _load_draft(path)
        if draft.modelo != modelo or draft.period != period:
            continue
        if draft.status is not FilingDraftStatus.APPROVED:
            continue
        candidates.append(draft)
    if not candidates:
        raise typer.BadParameter(
            (f"no APPROVED draft for modelo={modelo!r} period={period!r} under {drafts_dir}"),
        )
    candidates.sort(key=lambda d: d.approved_at or d.updated_at, reverse=True)
    return candidates[0]


def _resolve_draft(args: ReconcileCliArgs) -> FilingDraft:
    """Dispatch to the by-id or latest-approved resolver."""
    if args.last:
        if args.modelo is None or args.period is None:
            raise typer.BadParameter(
                "--last requires both --modelo and --period",
            )
        if args.draft_id is not None:
            raise typer.BadParameter(
                "pass a draft id OR --last, not both",
            )
        return _resolve_latest_approved(args.modelo, args.period)
    if args.draft_id is None:
        raise typer.BadParameter(
            "either a draft id or --last --modelo X --period Y is required",
        )
    return _resolve_draft_by_id(args.draft_id)


def _fetch_remote(
    *,
    draft: FilingDraft,
    fetcher: RemoteFilingFetcher | None,
) -> RemoteFiling | None:
    """Call the fetcher Protocol if one was injected; otherwise return ``None``.

    The CLI unit suite injects a Protocol-conforming Python class via
    the ``fetcher_provider`` registration seam; the production path
    (wired in Phase 5's sync-run orchestration) passes a real live
    fetcher. With no override, the CLI defaults to a single-draft dry
    look-up that surfaces ``NOT_YET_FOUND`` so Kent sees the
    warning-level narrative immediately rather than a silent empty
    run. When a fetcher is injected the multi-filing chain is reduced
    to the latest-by-``submitted_at`` anchor per the ADR flow.
    """
    if fetcher is None:
        return None
    filings = asyncio.run(fetcher.fetch_filing_detail(draft.modelo, draft.period))
    if not filings:
        return None
    ordered = sorted(filings, key=lambda filing: filing.submitted_at, reverse=True)
    return ordered[0]


def _render_report_human(report: ReconciliationReport, lang: Language) -> None:
    """Pretty-print a :class:`ReconciliationReport` to the console."""
    status_color = {
        ReconciliationStatus.MATCH: "green",
        ReconciliationStatus.DIVERGENT: "red",
        ReconciliationStatus.NOT_YET_FOUND: "yellow",
    }[report.status]
    _console.print(f"[bold {status_color}]{report.status.value.upper()}[/]")

    header = Table(title="Reconciliation", show_header=False)
    header.add_row("modelo", report.draft_ref.modelo)
    header.add_row("period", report.draft_ref.period)
    header.add_row("draft_id", report.draft_ref.draft_id)
    header.add_row("draft_status", report.draft_ref.status.value)
    if report.remote_ref is not None:
        header.add_row("expediente_id", report.remote_ref.expediente_id)
    header.add_row("reconciled_at", report.reconciled_at.isoformat())
    _console.print(header)

    if report.casilla_deltas:
        deltas_table = Table(title="Divergences")
        deltas_table.add_column("casilla")
        deltas_table.add_column("kind")
        deltas_table.add_column("local")
        deltas_table.add_column("remote")
        deltas_table.add_column("delta")
        deltas_table.add_column("narrative")
        for delta in report.casilla_deltas:
            deltas_table.add_row(
                delta.casilla_id,
                delta.kind.value,
                _format_value(delta.local_value),
                _format_value(delta.remote_value),
                _format_delta(delta.delta),
                _render_translatable(delta.narrative, lang),
            )
        _console.print(deltas_table)

    _console.print(_render_translatable(report.narrative, lang))


def _render_translatable(text: Translatable, lang: Language) -> str:
    """Render a trilingual :class:`Translatable` in Kent's active language."""
    return get_translation(text, lang)


def _format_value(value: str | None) -> str:
    """Render a nullable string payload for the deltas table."""
    return value if value not in (None, "") else "-"


def _format_delta(delta: object) -> str:
    """Render a signed monetary delta for the deltas table."""
    if delta is None:
        return "-"
    return str(delta)


def _emit_json(report: ReconciliationReport) -> None:
    """Serialise the report to stdout in deterministic JSON."""
    payload = report.model_dump(mode="json")
    typer.echo(_json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def _run(
    *,
    draft_id: str | None,
    modelo: str | None,
    period: str | None,
    last: bool,
    as_json: bool,
    dry_run: bool,
    argv: Sequence[str] | None,
    fetcher: RemoteFilingFetcher | None,
    now: Callable[[], datetime],
) -> None:
    """Execute the reconcile pipeline for one draft."""
    reject_forbidden_flags(argv if argv is not None else sys.argv[1:])
    _ = dry_run  # no-op alias; the command is read-only by construction.
    args = ReconcileCliArgs(
        draft_id=draft_id,
        modelo=modelo,
        period=period,
        last=last,
        as_json=as_json,
        dry_run=dry_run,
    )
    draft = _resolve_draft(args)
    try:
        filing = _fetch_remote(draft=draft, fetcher=fetcher)
    except AeatError as exc:
        _logger.error("live fetch failed: %s", exc)
        raise typer.Exit(code=4) from exc
    report = reconcile(draft, filing, now=now)

    if as_json:
        _emit_json(report)
    else:
        _render_report_human(report, _output_language())

    exit_code = _STATUS_TO_EXIT_CODE.get(report.status)
    if exit_code is None:  # pragma: no cover - exhaustive triad
        raise AssertionError(f"unhandled ReconciliationStatus: {report.status!r}")
    if as_json:
        return  # Machine consumers check the JSON body, not the exit code.
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def register(
    app: typer.Typer,
    *,
    fetcher_provider: Callable[[], RemoteFilingFetcher | None] = lambda: None,
    now_provider: Callable[[], Callable[[], datetime]] = lambda: lambda: datetime.now(tz=UTC),
) -> None:
    """Register the ``reconcile`` subcommand on the given ``app``.

    The providers are factory callables so unit tests can swap a
    Protocol-conforming fetcher and a frozen clock without touching
    module-level state.

    Args:
        app: The parent ``aeat filing`` :class:`typer.Typer` instance.
        fetcher_provider: Factory for the live remote fetcher; returns
            ``None`` by default so the CLI surfaces ``NOT_YET_FOUND``
            rather than attempting a live round-trip outside of the
            Phase-5 sync-run context.
        now_provider: Factory for the wall-clock callable handed to
            :func:`reconcile`.
    """

    @app.command(
        "reconcile",
        help=(
            "Compare an APPROVED filing draft against AEAT's authoritative "
            "record (read-only). Refuses every write-verb flag at parser "
            "level; see issue #116."
        ),
    )
    def reconcile_cmd(
        draft_id: Annotated[
            str | None,
            typer.Argument(
                help="Content-addressed filing-draft identifier to reconcile.",
            ),
        ] = None,
        modelo: Annotated[
            str | None,
            typer.Option(
                "--modelo",
                help="AEAT modelo code (used with --last to select a draft).",
            ),
        ] = None,
        period: Annotated[
            str | None,
            typer.Option(
                "--period",
                help="Period identifier (used with --last to select a draft).",
            ),
        ] = None,
        last: Annotated[
            bool,
            typer.Option(
                "--last",
                help="Pick the most recent APPROVED draft matching --modelo + --period.",
            ),
        ] = False,
        as_json: Annotated[
            bool,
            typer.Option(
                "--json",
                help="Emit the ReconciliationReport as JSON on stdout.",
            ),
        ] = False,
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help=("No-op compatibility alias; aeat filing reconcile is read-only by construction."),
            ),
        ] = False,
    ) -> None:
        """Run one reconciliation pass and report the Kent-observable status."""
        _run(
            draft_id=draft_id,
            modelo=modelo,
            period=period,
            last=last,
            as_json=as_json,
            dry_run=dry_run,
            argv=None,
            fetcher=fetcher_provider(),
            now=now_provider(),
        )


__all__ = [
    "ReconcileCliArgs",
    "register",
    "reject_forbidden_flags",
]
