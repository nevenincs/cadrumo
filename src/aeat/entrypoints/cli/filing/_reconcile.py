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
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ....adapters.outbound.aeat.auth._authenticator import AEAT_SESSION_IDLE_TTL, AeatSession
from ....adapters.outbound.aeat.auth._providers import AuthProviderKind, ClaveMovilSessionDetail
from ....adapters.outbound.aeat.sede import (
    ExpedienteNotFoundError,
    SedeCapture,
    SedeError,
    capture_declaration,
    capture_justificante,
    find_expediente,
    walk_declarations_register,
)
from ....application.filing._schema import FilingDraft, FilingDraftStatus
from ....application.filing.reconciliation import (
    ReconciliationReport,
    ReconciliationStatus,
    reconcile,
)
from ....core.config import Settings, load_settings
from ....core.logging import get_logger
from ....domain.justificante import parse_justificante
from .._errors import CliRefusedBoundaryError, json_output_requested
from .._schemas import OutputRootSchema, emit_json_success, register_schema
from ..auth import _session
from ..auth._paths import storage_state_paths

_logger = get_logger(__name__)
_CONSOLE = Console()


@register_schema("filing reconcile")
class FilingReconcileJson(OutputRootSchema[ReconciliationReport]):
    """Schema for ``aeat filing reconcile --json``."""


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


def reject_forbidden_flags(argv: tuple[str, ...], *, emit_json: bool = False) -> None:
    """Exit 2 on any write-implying flag before it reaches Typer.

    Defence-in-depth: Typer would reject the flag as unknown anyway,
    but pre-parsing makes the intent explicit and the error message
    Kent-actionable.
    """
    for token in argv:
        head = token.split("=", 1)[0]
        if head in _FORBIDDEN_FLAGS:
            message = f"{head!r} implies an AEAT mutation. `aeat filing reconcile` is strictly read-only."
            if emit_json:
                raise CliRefusedBoundaryError(message, context={"flag": head})
            _CONSOLE.print(f"[red]Refused: {message}[/red]")
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
    emit_json = json_output or json_output_requested()
    reject_forbidden_flags(tuple(ctx.args or ()), emit_json=emit_json)

    settings = load_settings()
    draft = _load_draft(
        settings,
        draft_id=draft_id,
        last=last,
        modelo=modelo,
        period=period,
        emit_json=emit_json,
    )

    resolved_ejercicio = ejercicio or _infer_ejercicio(draft.period, draft.modelo)
    if resolved_ejercicio is None:
        if emit_json:
            raise CliRefusedBoundaryError(
                "Could not infer tax year from draft period. Pass --ejercicio.",
                context={"modelo": draft.modelo, "period": draft.period},
            )
        _CONSOLE.print("[red]Could not infer tax year from draft period. Pass --ejercicio.[/red]")
        raise typer.Exit(code=2)

    try:
        report = asyncio.run(
            _run_reconcile(
                settings,
                draft=draft,
                modelo=draft.modelo,
                ejercicio=resolved_ejercicio,
                emit_json=emit_json,
            )
        )
    except ExpedienteNotFoundError:
        report = reconcile(draft, None, now=datetime.now(tz=UTC))
    except SedeError as exc:
        if emit_json:
            raise
        _CONSOLE.print(f"[red]sede walk failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if emit_json:
        emit_json_success("filing reconcile", report)
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
    emit_json: bool,
) -> FilingDraft:
    """Load a draft via :class:`FilingDraftRepository`.

    Drafts are ciphertext-at-rest only; the repository enforces the
    classification gate and version contract.
    """
    from ....application.filing._repository import FilingDraftRepository

    drafts_dir = Path(settings.aeat_drafts_dir)
    if not drafts_dir.is_dir():
        if emit_json:
            raise CliRefusedBoundaryError(
                f"Drafts directory missing: {drafts_dir}",
                context={"drafts_dir": str(drafts_dir)},
            )
        _CONSOLE.print(f"[red]Drafts directory missing: {drafts_dir}[/red]")
        raise typer.Exit(code=1)

    repository = FilingDraftRepository(store_dir=drafts_dir)

    if last:
        if not modelo or not period:
            if emit_json:
                raise CliRefusedBoundaryError(
                    "--last requires both --modelo and --period.",
                    context={"flag": "--last"},
                )
            raise typer.BadParameter("--last requires both --modelo and --period")
        candidates: list[FilingDraft] = []
        for draft in repository.iter_drafts():
            if draft.modelo != modelo or draft.period != period:
                continue
            if draft.status is FilingDraftStatus.APPROVED:
                candidates.append(draft)
        if not candidates:
            if emit_json:
                raise CliRefusedBoundaryError(
                    f"No APPROVED draft found for modelo={modelo} period={period}.",
                    context={"modelo": modelo, "period": period},
                )
            _CONSOLE.print(f"[yellow]No APPROVED draft found for modelo={modelo} period={period}.[/yellow]")
            raise typer.Exit(code=1)
        # Pick the most recent by mtime on the underlying envelope file.
        candidates.sort(
            key=lambda d: repository.envelope_path_for(d.draft_id).stat().st_mtime,
            reverse=True,
        )
        return candidates[0]

    if draft_id is None:
        if emit_json:
            raise CliRefusedBoundaryError(
                "Pass a draft-id argument, or use --last with --modelo / --period.",
            )
        raise typer.BadParameter("Pass a draft-id argument, or use --last with --modelo / --period.")
    loaded = repository.load(draft_id)
    if loaded is None:
        if emit_json:
            raise CliRefusedBoundaryError(
                f"Draft {draft_id!r} not found under {drafts_dir}.",
                context={"draft_id": draft_id, "drafts_dir": str(drafts_dir)},
            )
        _CONSOLE.print(f"[red]Draft {draft_id!r} not found under {drafts_dir}.[/red]")
        raise typer.Exit(code=1)
    return loaded


async def _run_reconcile(
    settings: Settings,
    *,
    draft: FilingDraft,
    modelo: str,
    ejercicio: int,
    emit_json: bool,
) -> ReconciliationReport:
    session = _resolve_session(settings, emit_json=emit_json)
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


def _resolve_session(settings: Settings, *, emit_json: bool) -> AeatSession:
    """Reconstruct a Clave-based AeatSession from the cached sidecar."""
    persisted = _session.load(settings, None)
    if persisted is None:
        if emit_json:
            raise CliRefusedBoundaryError(
                "No active AEAT session. Run `aeat auth login --provider clave_movil` first.",
            )
        _CONSOLE.print("[red]No active AEAT session. Run `aeat auth login --provider clave_movil` first.[/red]")
        raise typer.Exit(code=1)
    if persisted.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        if emit_json:
            raise CliRefusedBoundaryError(
                "Reconcile currently supports Cl@ve-móvil only.",
                context={"provider": persisted.provider_kind.value},
            )
        _CONSOLE.print(
            f"[yellow]Reconcile currently supports Cl@ve-móvil only; active provider is "
            f"{persisted.provider_kind.value}.[/yellow]"
        )
        raise typer.Exit(code=2)
    paths = storage_state_paths(settings, persisted.provider_kind)
    if not paths.storage_state.exists():
        if emit_json:
            raise CliRefusedBoundaryError(
                f"Session cookie file missing at {paths.storage_state}. Run `aeat auth login` to re-authenticate.",
                context={"storage_state": str(paths.storage_state)},
            )
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
