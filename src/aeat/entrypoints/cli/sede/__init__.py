"""Expose the ``aeat sede`` post-auth sede discovery sub-app.

Wires every read-only sede surface from
:mod:`aeat.adapters.outbound.aeat.sede` behind a Typer sub-app:

- ``aeat sede list-expedientes [--modelo M]`` walks *Mis Expedientes*
  (the procedure tree) and prints every leaf (id, modelo, ejercicio,
  category path).
- ``aeat sede list-declarations --modelo M --ejercicio Y`` drives the
  *Consultar declaraciones presentadas* form for one
  ``(modelo, ejercicio)`` query and prints one row per filing.
- ``aeat sede capture-declaration --modelo M --ejercicio Y --period P``
  fetches the raw justificante PDF for a single filing identified by
  ``(modelo, ejercicio, period)`` via the declaraciones-presentadas
  surface.
- ``aeat sede capture-corpus --modelos M[,M...] --ejercicios Y[,Y...]``
  captures every declaration the authenticated NIF has for each
  ``(modelo, ejercicio)`` pair; PDFs land under
  ``scratch/declarations-corpus/`` with a JSONL manifest.
- ``aeat sede discover [--modelo M]`` is a one-shot walker and capturer
  that emits a per-modelo report to stdout and writes every captured
  PDF under ``scratch/sede-discovery/<ts>/``.
- ``aeat sede notifications [--summary | --query]`` is a read-only walk
  of the AEAT notifications and messages surface (formal
  *Notificaciones* plus lighter-weight *Comunicaciones*).

Every subcommand is strictly read-only. The session keep-alive flow
(``aeat auth whoami``) is the caller's responsibility when a run crosses
AEAT's ~18-minute idle deadline encoded in
:data:`aeat.adapters.outbound.aeat.auth.AEAT_SESSION_IDLE_TTL`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ....adapters.inbound.justificante import parse_justificante
from ....adapters.outbound.aeat.auth import (
    AEAT_SESSION_IDLE_TTL,
    AeatSession,
    AuthProviderKind,
    ClaveMovilSessionDetail,
)
from ....adapters.outbound.aeat.sede import (
    Expediente,
    NotificationsSnapshot,
    SedeError,
    capture_declaration,
    capture_justificante,
    fetch_notifications_query,
    fetch_notifications_summary,
    shared_playwright,
    walk_declarations_register,
    walk_expedientes_tree,
)
from ....core.config import load_settings
from ....core.logging import get_logger
from .._errors import json_output_requested
from .._schemas import OutputRootSchema, emit_json_success, register_schema
from ..auth import _session
from ..auth._paths import storage_state_paths

log = get_logger(__name__)

app = typer.Typer(
    name="sede",
    help="Post-auth AEAT sede discovery (read-only).",
    no_args_is_help=True,
)

_CONSOLE = Console()


@register_schema("sede list-expedientes")
class SedeListExpedientesJson(OutputRootSchema[list[Expediente]]):
    """JSON output schema for ``aeat sede list-expedientes --json``.

    Wraps a list of
    :class:`aeat.adapters.outbound.aeat.sede.Expediente` rows.
    """


@register_schema("sede notifications")
class SedeNotificationsJson(OutputRootSchema[NotificationsSnapshot]):
    """JSON output schema for ``aeat sede notifications --json``.

    Wraps a
    :class:`aeat.adapters.outbound.aeat.sede.NotificationsSnapshot`.
    """


def _require_active_session() -> AeatSession:
    """Load the cached AEAT session or exit with a helpful message.

    Returns a lightweight
    :class:`aeat.adapters.outbound.aeat.auth.AeatSession` bound to the
    on-disk ``storage_state`` path. The sede walker only consumes
    :attr:`AeatSession.storage_state_path` and
    :attr:`AeatSession.identity_nif`, so the reconstructed session does
    not need provider-specific handshake detail.

    Returns:
        The reconstructed session.

    Raises:
        :exc:`aeat.adapters.outbound.aeat.sede.SedeError`: When ``--json``
            output is active and no session exists or the cookie file is
            missing.
        typer.Exit: With code ``1`` (no session) or ``2`` (non-Cl@ve-móvil
            provider) for the rich-output paths.
    """
    settings = load_settings()
    persisted = _session.load(settings, None)
    if persisted is None:
        if json_output_requested():
            raise SedeError("No active AEAT session. Run `aeat auth login` first.")
        _CONSOLE.print("[red]No active AEAT session. Run `aeat auth login` first.[/red]")
        raise typer.Exit(code=1)
    paths = storage_state_paths(settings, persisted.provider_kind)
    storage_path = paths.storage_state
    if not storage_path.exists():
        if json_output_requested():
            raise SedeError(f"Session cookie file missing at {storage_path}. Run `aeat auth login` to re-authenticate.")
        _CONSOLE.print(
            f"[red]Session cookie file missing at {storage_path}. Run `aeat auth login` to re-authenticate.[/red]"
        )
        raise typer.Exit(code=1)
    if persisted.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        if json_output_requested():
            raise SedeError(
                "aeat sede currently only supports Cl@ve-móvil sessions; "
                "certificate and other providers are a follow-up."
            )
        _CONSOLE.print(
            f"[yellow]aeat sede currently only supports Cl@ve-móvil sessions "
            f"(active provider: {persisted.provider_kind.value}). Certificate and "
            "other provider support is a follow-up.[/yellow]"
        )
        raise typer.Exit(code=2)
    detail = ClaveMovilSessionDetail(
        dni_nie=persisted.identity_nif,
        used_non_qr_fallback=True,
        verification_code=None,
    )
    return AeatSession(
        provider_kind=persisted.provider_kind,
        authenticated_at=persisted.authenticated_at,
        idle_deadline=persisted.authenticated_at + AEAT_SESSION_IDLE_TTL,
        storage_state_path=storage_path,
        identity_nif=persisted.identity_nif,
        provider_detail=detail,
    )


@app.command(
    "list-expedientes",
    help="Walk the authenticated expedientes tree and print every leaf.",
)
def list_expedientes(
    modelo: Annotated[
        str | None,
        typer.Option(
            "--modelo",
            "-m",
            help="Only list expedientes whose category label references this modelo code.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON instead of a human table."),
    ] = False,
) -> None:
    """Walk *Mis Expedientes* and print every leaf row.

    Args:
        modelo: When supplied, only list expedientes whose category label
            references this modelo code.
        json_output: When ``True``, emit JSON instead of a human table.
    """
    session = _require_active_session()
    try:
        expedientes = asyncio.run(walk_expedientes_tree(session, modelo=modelo))
    except SedeError as exc:
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]sede walk failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output or json_output_requested():
        emit_json_success("sede list-expedientes", expedientes)
        return

    table = Table(title=f"AEAT expedientes ({len(expedientes)})")
    table.add_column("expediente_id")
    table.add_column("modelo")
    table.add_column("ejercicio")
    table.add_column("category (leaf)")
    for expediente in expedientes:
        leaf = expediente.category_path[-1] if expediente.category_path else ""
        table.add_row(
            expediente.expediente_id,
            expediente.modelo or "?",
            str(expediente.ejercicio) if expediente.ejercicio is not None else "?",
            leaf[:70],
        )
    _CONSOLE.print(table)


@app.command(
    "list-declarations",
    help="Drive the 'Consultar declaraciones presentadas' form for one (modelo, ejercicio).",
)
def list_declarations(
    modelo: Annotated[
        str,
        typer.Option(
            "--modelo",
            "-m",
            help="Modelo code to query (e.g. 100, 130, 303, 390, 111, 190).",
        ),
    ],
    ejercicio: Annotated[
        int,
        typer.Option(
            "--ejercicio",
            "-e",
            help="Tax year to query (e.g. 2024).",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON instead of a human table."),
    ] = False,
) -> None:
    """Walk the declaraciones register for a single ``(modelo, ejercicio)``.

    Args:
        modelo: Modelo code to query (e.g. ``100``, ``130``, ``303``).
        ejercicio: Tax year to query (e.g. ``2024``).
        json_output: When ``True``, emit JSON instead of a human table.
    """
    session = _require_active_session()
    try:
        declarations = asyncio.run(
            walk_declarations_register(session, modelo=modelo, ejercicio=ejercicio),
        )
    except SedeError as exc:
        _CONSOLE.print(f"[red]declarations walk failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        payload = [d.model_dump(mode="json") for d in declarations]
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return

    table = Table(title=f"Declaraciones presentadas — Modelo {modelo} / {ejercicio} ({len(declarations)})")
    table.add_column("expediente_id")
    table.add_column("period")
    table.add_column("estado")
    table.add_column("presented_at")
    table.add_column("just")
    for d in declarations:
        table.add_row(
            d.expediente_id,
            d.period,
            d.estado,
            d.presented_at.strftime("%Y-%m-%d %H:%M:%S"),
            d.justificante_link_text or "",
        )
    _CONSOLE.print(table)


@app.command(
    "capture-declaration",
    help="Fetch one declaration's justificante PDF by (modelo, ejercicio, period).",
)
def capture_declaration_cmd(
    modelo: Annotated[
        str,
        typer.Option("--modelo", "-m", help="Modelo code (e.g. 100, 130, 303, 390, 111, 190)."),
    ],
    ejercicio: Annotated[
        int,
        typer.Option("--ejercicio", "-e", help="Tax year to query (e.g. 2024)."),
    ],
    period: Annotated[
        str,
        typer.Option(
            "--period",
            "-p",
            help="Period token to filter on (0A annual, 1T-4T quarterly, 01-12 monthly).",
        ),
    ],
    output_path: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Where to write the captured PDF.",
        ),
    ],
) -> None:
    """Drive the declaraciones register, locate the matching row, and capture the PDF.

    Args:
        modelo: Modelo code (e.g. ``100``, ``130``, ``303``).
        ejercicio: Tax year to query (e.g. ``2024``).
        period: Period token to filter on (``0A`` annual, ``1T``-``4T``
            quarterly, ``01``-``12`` monthly).
        output_path: Where to write the captured PDF.

    Raises:
        :exc:`aeat.adapters.outbound.aeat.sede.SedeError`: When no
            matching declaration exists or the capture fails.
        typer.Exit: With code ``1`` on capture failure.
    """
    session = _require_active_session()

    async def _run() -> tuple[bytes, str]:
        rows = await walk_declarations_register(session, modelo=modelo, ejercicio=ejercicio)
        match = [r for r in rows if r.period == period]
        if not match:
            available = ", ".join(sorted({r.period for r in rows})) or "(none)"
            raise SedeError(
                f"no Modelo {modelo} declaration for {ejercicio}/{period}; available periods: {available}",
            )
        if len(match) > 1:
            log.warning(
                "%d declarations match modelo=%s ejercicio=%s period=%s; using the first",
                len(match),
                modelo,
                ejercicio,
                period,
            )
        capture = await capture_declaration(session, match[0])
        return capture.pdf_bytes, capture.ref.csv

    try:
        pdf_bytes, csv = asyncio.run(_run())
    except SedeError as exc:
        _CONSOLE.print(f"[red]capture failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    output_path.write_bytes(pdf_bytes)
    _CONSOLE.print(
        f"[green]Captured Modelo {modelo} {ejercicio}/{period}:[/green] "
        f"{output_path} ({len(pdf_bytes)} bytes, csv={csv})",
    )


@app.command(
    "capture-corpus",
    help="Capture every declaration for the authenticated NIF across "
    "(modelo, ejercicio) tuples and write PDFs to scratch/.",
)
def capture_corpus_cmd(
    modelos: Annotated[
        str,
        typer.Option(
            "--modelos",
            help="Comma-separated modelo codes (e.g. 100,130,303,390,111,190).",
        ),
    ] = "100,130,303,390,111,190",
    ejercicios: Annotated[
        str,
        typer.Option(
            "--ejercicios",
            help="Comma-separated tax years (e.g. 2021,2022,2023,2024).",
        ),
    ] = "2021,2022,2023,2024",
    output_root: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Root directory for captures.",
        ),
    ] = Path("scratch/declarations-corpus"),
    skip_existing: Annotated[
        bool,
        typer.Option(
            "--skip-existing/--overwrite",
            help="Skip PDFs already present on disk (default) or re-fetch.",
        ),
    ] = True,
    delay_seconds: Annotated[
        float,
        typer.Option(
            "--delay-seconds",
            help="Sleep between iterations (anti-throttle pacing). Default 1.0s; pass 0 to disable.",
            min=0.0,
        ),
    ] = 1.0,
) -> None:
    """Walk every ``(modelo, ejercicio)`` tuple and capture every declaration.

    Each iteration is wrapped in a broad :exc:`Exception` catch so a
    transient Playwright timeout on one query does not abort the entire
    corpus. ``--delay-seconds`` paces the loop to reduce the chance of
    AEAT's anti-bot heuristics flagging the run.

    Args:
        modelos: Comma-separated modelo codes (e.g.
            ``100,130,303,390,111,190``).
        ejercicios: Comma-separated tax years (e.g.
            ``2021,2022,2023,2024``).
        output_root: Root directory for captures.
        skip_existing: When ``True`` (default), skip PDFs already present
            on disk; otherwise re-fetch.
        delay_seconds: Sleep between iterations (anti-throttle pacing).

    Raises:
        :exc:`aeat.adapters.outbound.aeat.sede.SedeError`: When a fatal
            sede error aborts the corpus run (per-iteration errors are
            recorded in the summary instead).
        typer.Exit: With code ``1`` on fatal failure.
    """
    session = _require_active_session()
    output_root.mkdir(parents=True, exist_ok=True)
    modelo_list = [m.strip() for m in modelos.split(",") if m.strip()]
    ejercicio_list = [int(y.strip()) for y in ejercicios.split(",") if y.strip()]

    async def _run() -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        first_iter = True
        # Bulk loop: hoist Playwright startup OUT of every walker /
        # capture call so the corpus pays one ~1s startup cost
        # instead of ~1s per (modelo, ejercicio) tuple + per row.
        async with shared_playwright(session) as pw:
            for modelo in modelo_list:
                for ejercicio in ejercicio_list:
                    if not first_iter and delay_seconds > 0:
                        await asyncio.sleep(delay_seconds)
                    first_iter = False
                    try:
                        declarations = await walk_declarations_register(
                            session,
                            modelo=modelo,
                            ejercicio=ejercicio,
                            playwright=pw,
                        )
                    except Exception as exc:
                        rows.append(
                            {
                                "modelo": modelo,
                                "ejercicio": ejercicio,
                                "status": "walk_failed",
                                "error": f"{type(exc).__name__}: {exc}",
                            },
                        )
                        continue
                    for idx, declaration in enumerate(declarations):
                        if delay_seconds > 0:
                            await asyncio.sleep(delay_seconds)
                        target = output_root / f"m{modelo}-{ejercicio}-{declaration.period}-{idx}.pdf"
                        if skip_existing and target.is_file():
                            rows.append(
                                {
                                    "modelo": modelo,
                                    "ejercicio": ejercicio,
                                    "period": declaration.period,
                                    "expediente_id": declaration.expediente_id,
                                    "path": str(target),
                                    "status": "cached",
                                },
                            )
                            continue
                        try:
                            capture = await capture_declaration(session, declaration, playwright=pw)
                        except Exception as exc:
                            rows.append(
                                {
                                    "modelo": modelo,
                                    "ejercicio": ejercicio,
                                    "period": declaration.period,
                                    "expediente_id": declaration.expediente_id,
                                    "status": "capture_failed",
                                    "error": f"{type(exc).__name__}: {exc}",
                                },
                            )
                            continue
                        target.write_bytes(capture.pdf_bytes)
                        rows.append(
                            {
                                "modelo": modelo,
                                "ejercicio": ejercicio,
                                "period": declaration.period,
                                "expediente_id": declaration.expediente_id,
                                "path": str(target),
                                "csv": capture.ref.csv,
                                "sha256": capture.pdf_sha256,
                                "status": "captured",
                            },
                        )
        return rows

    try:
        results = asyncio.run(_run())
    except SedeError as exc:
        _CONSOLE.print(f"[red]capture-corpus failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    summary_path = output_root / "_capture-summary.json"
    summary_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    captured = sum(1 for r in results if r.get("status") == "captured")
    cached = sum(1 for r in results if r.get("status") == "cached")
    walk_failed = sum(1 for r in results if r.get("status") == "walk_failed")
    capture_failed = sum(1 for r in results if r.get("status") == "capture_failed")
    _CONSOLE.print(
        f"[green]capture-corpus done:[/green] "
        f"captured={captured} cached={cached} "
        f"walk_failed={walk_failed} capture_failed={capture_failed}; "
        f"summary at {summary_path}",
    )


@app.command(
    "discover",
    help="Walk the sede, capture every justificante for --modelo (or all), write PDFs to scratch/.",
)
def discover(
    modelo: Annotated[
        str | None,
        typer.Option(
            "--modelo",
            "-m",
            help="Restrict discovery to this modelo code; omit to capture every expediente.",
        ),
    ] = None,
    output_root: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Output directory for captures (default: scratch/sede-discovery/<utc-timestamp>/).",
        ),
    ] = Path("scratch/sede-discovery"),
) -> None:
    """Capture PDFs and parsed metadata for every matching expediente.

    Args:
        modelo: Restrict discovery to this modelo code; omit to capture
            every expediente.
        output_root: Output directory for captures (default
            ``scratch/sede-discovery/<utc-timestamp>/``).

    Raises:
        :exc:`aeat.adapters.outbound.aeat.sede.SedeError`: When the
            initial expediente walk fails fatally.
        typer.Exit: With code ``1`` on discovery failure.
    """
    session = _require_active_session()
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    async def _run() -> list[dict[str, object]]:
        expedientes: tuple[Expediente, ...] = await walk_expedientes_tree(session, modelo=modelo)
        reports: list[dict[str, object]] = []
        for expediente in expedientes:
            report: dict[str, object] = {
                "expediente_id": expediente.expediente_id,
                "modelo": expediente.modelo,
                "ejercicio": expediente.ejercicio,
                "category_leaf": (expediente.category_path[-1] if expediente.category_path else None),
            }
            try:
                capture = await capture_justificante(session, expediente)
            except SedeError as exc:
                report["status"] = "capture_failed"
                report["error"] = str(exc)
                reports.append(report)
                continue

            modelo_slug = expediente.modelo or "unknown"
            exp_dir = run_dir / modelo_slug / expediente.expediente_id
            exp_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = exp_dir / "justificante.pdf"
            pdf_path.write_bytes(capture.pdf_bytes)
            pdf_sha = hashlib.sha256(capture.pdf_bytes).hexdigest()
            report["pdf_path"] = str(pdf_path)
            report["pdf_sha256"] = pdf_sha
            report["csv"] = capture.ref.csv

            try:
                justificante = parse_justificante(pdf_path)
            except Exception as exc:
                report["status"] = "parsed_failed"
                report["parse_error"] = f"{type(exc).__name__}: {exc}"
                reports.append(report)
                continue

            report["status"] = "captured"
            report["justificante"] = justificante.model_dump(mode="json")
            reports.append(report)
        return reports

    try:
        reports = asyncio.run(_run())
    except SedeError as exc:
        _CONSOLE.print(f"[red]discovery failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    report_path = run_dir / "discovery-report.json"
    report_path.write_text(json.dumps(reports, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    captured = sum(1 for r in reports if r.get("status") == "captured")
    _CONSOLE.print(f"[green]sede discover: {captured}/{len(reports)} expedientes captured → {run_dir}[/green]")
    if captured < len(reports):
        for r in reports:
            if r.get("status") != "captured":
                _CONSOLE.print(
                    f"  [yellow]{r['expediente_id']}: {r.get('status')} — "
                    f"{r.get('error') or r.get('parse_error')}[/yellow]"
                )


@app.command(
    "notifications",
    help="Walk AEAT's notifications/messages surface (read-only).",
)
def notifications(
    summary_only: Annotated[
        bool,
        typer.Option(
            "--summary",
            help="Use the unread-summary endpoint (cheaper, smaller column set).",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON instead of a human table."),
    ] = False,
) -> None:
    """Print every notification and communication AEAT has on file.

    Args:
        summary_only: When ``True``, use the unread-summary endpoint
            (cheaper, smaller column set) instead of the full query.
        json_output: When ``True``, emit JSON instead of a human table.
    """
    session = _require_active_session()
    fetch = fetch_notifications_summary if summary_only else fetch_notifications_query
    try:
        snapshot = asyncio.run(fetch(session))
    except SedeError as exc:
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]notifications fetch failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output or json_output_requested():
        emit_json_success("sede notifications", snapshot)
        return

    title = "AEAT notifications (summary)" if summary_only else "AEAT notifications (query)"
    table = Table(title=f"{title} — {len(snapshot.rows)} row(s)")
    table.add_column("certificado")
    table.add_column("tipo")
    table.add_column("concepto")
    table.add_column("fecha emision")
    table.add_column("leida")
    for row in snapshot.rows:
        leida_text = "—" if row.leida is None else ("✓" if row.leida else "✗")
        table.add_row(
            row.certificado_id,
            row.tipo,
            row.concepto[:60],
            row.fecha_emision.isoformat(),
            leida_text,
        )
    _CONSOLE.print(table)
