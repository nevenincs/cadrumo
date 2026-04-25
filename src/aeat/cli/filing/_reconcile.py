"""``aeat filing reconcile`` — compare a local draft against AEAT's record (#239).

Wires the Kent-observable triad:

    FilingDraft on disk  →  aeat.sede walk + CSV → PDF
                         →  aeat.justificante parse
                         →  aeat.filing.reconciliation.reconcile
                         →  MATCH / DIVERGENT / NOT_YET_FOUND

The subcommand is strictly read-only: every AEAT touch goes through
`aeat.sede` (whose write-guard ban is enforced by the per-subpackage
grep test). No flag on this command may imply submission, amendment,
or any state-changing action.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ...auth._authenticator import AEAT_SESSION_IDLE_TTL, AeatSession
from ...auth._providers import AuthProviderKind, ClaveMovilSessionDetail
from ...config import Settings, load_settings
from ...filing._schema import FilingDraft, FilingDraftStatus
from ...filing.reconciliation import (
    ReconciliationReport,
    ReconciliationStatus,
    reconcile,
)
from ...justificante import parse_justificante
from ...logging import get_logger
from ...sede import (
    ExpedienteNotFoundError,
    SedeCapture,
    SedeError,
    capture_declaration,
    capture_justificante,
    find_expediente,
    walk_declarations_register,
)
from ..auth import _session
from ..auth._paths import storage_state_paths

_logger = get_logger(__name__)
_CONSOLE = Console()

# Forbidden flags — parsed before Typer dispatch; any match hard-
# exits with code 2. Mirror of the previous write-guard implementation
# so `aeat filing reconcile --write` (or any cognate) can never reach
# the reconcile engine.
_FORBIDDEN_FLAGS: tuple[str, ...] = (
    "--write",
    "--submit",
    "--enviar",
    "--presentar",
    "--firmar",
    "--modificar",
    "--anular",
    "--send",
    "--commit",
)


def reject_forbidden_flags(argv: tuple[str, ...]) -> None:
    """Exit 2 on any write-implying flag before it reaches Typer.

    Defence-in-depth: Typer would reject the flag as unknown anyway,
    but pre-parsing makes the intent explicit and the error message
    Kent-actionable.
    """
    for token in argv:
        head = token.split("=", 1)[0]
        if head in _FORBIDDEN_FLAGS:
            _CONSOLE.print(
                f"[red]Refused: {head!r} implies an AEAT mutation. `aeat filing reconcile` is strictly read-only.[/red]"
            )
            raise typer.Exit(code=2)


def register(app: typer.Typer) -> None:
    """Register the ``reconcile`` subcommand on the filing Typer app."""
    app.command(
        name="reconcile",
        help="Compare a local draft against AEAT's authoritative record (#239).",
    )(_reconcile_cmd)


def _reconcile_cmd(
    ctx: typer.Context,
    draft_id: Annotated[
        str | None,
        typer.Argument(help="Draft identifier on disk; omit with --last."),
    ] = None,
    last: Annotated[
        bool,
        typer.Option("--last", help="Resolve the most recent APPROVED draft for --modelo + --period."),
    ] = False,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", "-m", help="Modelo code (required with --last)."),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", "-p", help="Period identifier (required with --last)."),
    ] = None,
    ejercicio: Annotated[
        int | None,
        typer.Option(
            "--ejercicio",
            help="Tax year (4 digits). Defaults to the 4-digit prefix of the draft period.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the ReconciliationReport as JSON."),
    ] = False,
) -> None:
    """Load a draft, fetch AEAT's record, reconcile, render the triad."""
    reject_forbidden_flags(tuple(ctx.args or ()))

    settings = load_settings()
    draft = _load_draft(
        settings,
        draft_id=draft_id,
        last=last,
        modelo=modelo,
        period=period,
    )

    resolved_ejercicio = ejercicio or _infer_ejercicio(draft.period, draft.modelo)
    if resolved_ejercicio is None:
        _CONSOLE.print("[red]Could not infer tax year from draft period. Pass --ejercicio.[/red]")
        raise typer.Exit(code=2)

    try:
        report = asyncio.run(
            _run_reconcile(
                settings,
                draft=draft,
                modelo=draft.modelo,
                ejercicio=resolved_ejercicio,
            )
        )
    except ExpedienteNotFoundError:
        report = reconcile(draft, None, now=datetime.now(tz=UTC))
    except SedeError as exc:
        _CONSOLE.print(f"[red]sede walk failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        # Write directly to sys.stdout's buffer in UTF-8 — typer.echo
        # (and the underlying click.echo) re-encode through stdout's
        # locale codec, which on Windows is cp1252 by default and
        # cannot encode the Hungarian Translatable narrative ("ő",
        # U+0151). Bypassing the codec is the safest fix.
        rendered = json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False)
        _write_json_utf8(rendered)
    else:
        _render_report(report)

    raise typer.Exit(code=_exit_code_for(report.status))


def _load_draft(
    settings: Settings,
    *,
    draft_id: str | None,
    last: bool,
    modelo: str | None,
    period: str | None,
) -> FilingDraft:
    drafts_dir = Path(settings.aeat_drafts_dir)
    if not drafts_dir.is_dir():
        _CONSOLE.print(f"[red]Drafts directory missing: {drafts_dir}[/red]")
        raise typer.Exit(code=1)

    if last:
        if not modelo or not period:
            raise typer.BadParameter("--last requires both --modelo and --period")
        candidates = sorted(
            drafts_dir.glob(f"{modelo}_{period}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            draft = FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
            if draft.status is FilingDraftStatus.APPROVED:
                return draft
        _CONSOLE.print(f"[yellow]No APPROVED draft found for modelo={modelo} period={period}.[/yellow]")
        raise typer.Exit(code=1)

    if draft_id is None:
        raise typer.BadParameter("Pass a draft-id argument, or use --last with --modelo / --period.")
    matches = list(drafts_dir.glob(f"*_*_{draft_id}.json"))
    if not matches:
        _CONSOLE.print(f"[red]Draft {draft_id!r} not found under {drafts_dir}.[/red]")
        raise typer.Exit(code=1)
    return FilingDraft.model_validate_json(matches[0].read_text(encoding="utf-8"))


def _write_json_utf8(rendered: str) -> None:
    """Emit ``rendered`` to stdout as UTF-8, bypassing the locale codec.

    On Windows the default stdout encoding is cp1252 which cannot
    represent characters outside Latin-1. Trilingual narratives in
    :class:`ReconciliationReport` (Spanish / English / Hungarian)
    legitimately carry such characters (Hungarian "ő" U+0151).
    Writing directly to ``sys.stdout.buffer`` keeps the output a
    valid UTF-8 byte stream regardless of the surrounding shell.
    """
    import sys as _sys

    payload = (rendered + "\n").encode("utf-8")
    buffer = getattr(_sys.stdout, "buffer", None)
    if buffer is None:
        # Fallback when stdout is replaced by a non-binary stream
        # (e.g. typer's CliRunner). Best-effort write — the runner
        # will reassemble bytes through its own decoder.
        _sys.stdout.write(rendered + "\n")
        return
    buffer.write(payload)
    buffer.flush()


async def _run_reconcile(
    settings: Settings,
    *,
    draft: FilingDraft,
    modelo: str,
    ejercicio: int,
) -> ReconciliationReport:
    session = _resolve_session(settings)
    capture = await _capture_for_filing(
        session,
        draft=draft,
        modelo=modelo,
        ejercicio=ejercicio,
        settings=settings,
    )
    with tempfile.TemporaryDirectory(prefix="aeat-reconcile-") as tmp:
        pdf_path = Path(tmp) / f"{capture.expediente.expediente_id}.pdf"
        pdf_path.write_bytes(capture.pdf_bytes)
        justificante = parse_justificante(pdf_path)
    return reconcile(draft, justificante, now=datetime.now(tz=UTC))


async def _capture_for_filing(
    session: AeatSession,
    *,
    draft: FilingDraft,
    modelo: str,
    ejercicio: int,
    settings: Settings,
) -> SedeCapture:
    """Try the procedure tree first, fall back to the declarations register.

    `aeat.sede.find_expediente` walks Mis Expedientes which exposes
    procedure-related filings (some IRPF anuales, sanciones, recursos).
    Quarterly modelos (M130, M303, M111, ...) are typically NOT in
    that tree — their authoritative record lives in
    *Consultar declaraciones presentadas*. This helper tries the
    procedure tree first (cheaper / older code path) and falls back
    to ``walk_declarations_register`` + ``capture_declaration`` when
    no procedure-tree expediente exists. Both code paths are
    strictly read-only.

    Raises:
        ExpedienteNotFoundError: When neither path locates a filing
            for the (modelo, ejercicio, draft.period) tuple. The
            caller catches this and emits NOT_YET_FOUND.
    """
    try:
        expediente = await find_expediente(
            session,
            modelo=modelo,
            ejercicio=ejercicio,
            settings=settings,
        )
        return await capture_justificante(session, expediente, settings=settings)
    except ExpedienteNotFoundError:
        # Fall back to the declarations-presentadas register —
        # this is where quarterly modelos live.
        declarations = await walk_declarations_register(
            session,
            modelo=modelo,
            ejercicio=ejercicio,
            settings=settings,
        )
        target_period = _normalise_period_for_register(draft.period)
        for declaration in declarations:
            if _normalise_period_for_register(declaration.period) == target_period:
                return await capture_declaration(session, declaration, settings=settings)
        raise


def _normalise_period_for_register(period: str) -> str:
    """Strip whitespace and uppercase for tolerant register matching."""
    return period.strip().upper()


def _resolve_session(settings: Settings) -> AeatSession:
    """Reconstruct a Clave-based AeatSession from the cached sidecar."""
    persisted = _session.load(settings, None)
    if persisted is None:
        _CONSOLE.print("[red]No active AEAT session. Run `aeat auth login --provider clave_movil` first.[/red]")
        raise typer.Exit(code=1)
    if persisted.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        _CONSOLE.print(
            f"[yellow]Reconcile currently supports Cl@ve-móvil only; active provider is "
            f"{persisted.provider_kind.value}.[/yellow]"
        )
        raise typer.Exit(code=2)
    paths = storage_state_paths(settings, persisted.provider_kind)
    if not paths.storage_state.exists():
        _CONSOLE.print(
            f"[red]Session cookie file missing at {paths.storage_state}. "
            "Run `aeat auth login` to re-authenticate.[/red]"
        )
        raise typer.Exit(code=1)
    return AeatSession(
        provider_kind=persisted.provider_kind,
        authenticated_at=persisted.authenticated_at,
        idle_deadline=persisted.authenticated_at + AEAT_SESSION_IDLE_TTL,
        storage_state_path=paths.storage_state,
        identity_nif=persisted.identity_nif,
        provider_detail=ClaveMovilSessionDetail(
            dni_nie=persisted.identity_nif,
            used_non_qr_fallback=True,
            verification_code=None,
        ),
    )


def _infer_ejercicio(period: str, modelo: str) -> int | None:
    """Infer the 4-digit tax year from the draft's period token."""
    del modelo  # Reserved for future modelo-specific period conventions.
    if period.isdigit() and len(period) == 4:
        try:
            return int(period)
        except ValueError:
            return None
    # Quarterly / monthly codes lead with the year: "2024Q1", "2024-03".
    prefix = period[:4]
    try:
        year = int(prefix)
    except ValueError:
        return None
    if 2000 <= year <= 2099:
        return year
    return None


def _render_report(report: ReconciliationReport) -> None:
    status_colour = {
        ReconciliationStatus.MATCH: "green",
        ReconciliationStatus.DIVERGENT: "red",
        ReconciliationStatus.NOT_YET_FOUND: "yellow",
    }[report.status]
    _CONSOLE.print(f"[{status_colour}]Status: {report.status.value.upper()}[/{status_colour}]")
    _CONSOLE.print(
        f"Draft: modelo={report.draft_ref.modelo} period={report.draft_ref.period} "
        f"tax_id={report.draft_ref.profile_tax_id}"
    )
    if report.justificante is not None:
        _CONSOLE.print(
            f"AEAT: modelo={report.justificante.modelo} period={report.justificante.period} "
            f"CSV={report.justificante.csv}"
        )
        _CONSOLE.print(f"Presented at: {report.justificante.presented_at.isoformat()}")
    if report.mismatches:
        table = Table(title=f"{len(report.mismatches)} divergences")
        table.add_column("kind")
        table.add_column("field")
        table.add_column("draft")
        table.add_column("AEAT")
        for m in report.mismatches:
            table.add_row(m.kind.value, m.field_name, m.draft_value, m.remote_value)
        _CONSOLE.print(table)
    es = report.narrative.get("es", "")
    if es:
        _CONSOLE.print(f"[italic]{es}[/italic]")


def _exit_code_for(status: ReconciliationStatus) -> int:
    if status is ReconciliationStatus.MATCH:
        return 0
    if status is ReconciliationStatus.NOT_YET_FOUND:
        return 4  # Kent-pattern: filing missing from AEAT.
    return 3  # DIVERGENT.


__all__ = ["register"]
