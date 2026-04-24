"""``aeat sede`` sub-app — post-auth sede discovery CLI (#239).

Subcommands:

- ``aeat sede list-expedientes [--modelo M]`` — walk the authenticated
  expedientes tree and print every leaf (id, modelo, ejercicio,
  category path).
- ``aeat sede capture <expediente-id>`` — resolve the CSV for one
  expediente and fetch the raw justificante PDF into a local file.
- ``aeat sede discover [--modelo M]`` — one-shot walker+capturer that
  emits a per-modelo :class:`DiscoveryReport` to stdout and writes
  every captured PDF under ``scratch/sede-discovery/<ts>/``. This is
  the continuous-growth entry point.
- ``aeat sede notifications [--summary | --query]`` — read-only walk
  of the AEAT notifications/messages surface (formal *Notificaciones*
  + lighter-weight *Comunicaciones*).

Every subcommand is strictly read-only. The session keep-alive flow
(``aeat auth whoami``) is the caller's responsibility when a run
crosses AEAT's ~18-minute idle deadline.
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

from ...auth._authenticator import (
    AEAT_SESSION_IDLE_TTL,
    AeatSession,
)
from ...auth._providers import (
    AuthProviderKind,
    ClaveMovilSessionDetail,
)
from ...config import load_settings
from ...justificante import parse_justificante
from ...logging import get_logger
from ...sede import (
    Expediente,
    SedeError,
    capture_justificante,
    fetch_notifications_query,
    fetch_notifications_summary,
    walk_expedientes_tree,
)
from ..auth import _session
from ..auth._paths import storage_state_paths

log = get_logger(__name__)

app = typer.Typer(
    name="sede",
    help="Post-auth AEAT sede discovery (read-only, #239).",
    no_args_is_help=True,
)

_CONSOLE = Console()


def _require_active_session() -> AeatSession:
    """Load the cached AEAT session or exit with a helpful message.

    Returns a lightweight :class:`AeatSession` bound to the on-disk
    ``storage_state`` path. The sede walker only consumes
    ``storage_state_path`` / ``identity_nif``, so the reconstructed
    session doesn't need provider-specific handshake detail.
    """
    settings = load_settings()
    persisted = _session.load(settings, None)
    if persisted is None:
        _CONSOLE.print("[red]No active AEAT session. Run `aeat auth login` first.[/red]")
        raise typer.Exit(code=1)
    paths = storage_state_paths(settings, persisted.provider_kind)
    storage_path = paths.storage_state
    if not storage_path.exists():
        _CONSOLE.print(
            f"[red]Session cookie file missing at {storage_path}. Run `aeat auth login` to re-authenticate.[/red]"
        )
        raise typer.Exit(code=1)
    if persisted.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
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
    """Walk Mis Expedientes and print every leaf row."""
    session = _require_active_session()
    try:
        expedientes = asyncio.run(walk_expedientes_tree(session, modelo=modelo))
    except SedeError as exc:
        _CONSOLE.print(f"[red]sede walk failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        payload = [e.model_dump(mode="json") for e in expedientes]
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
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
    """Capture PDFs + parsed metadata for every matching expediente."""
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
    report_path.write_text(
        json.dumps(reports, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
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
    """Print every notification + communication AEAT has on file."""
    session = _require_active_session()
    fetch = fetch_notifications_summary if summary_only else fetch_notifications_query
    try:
        snapshot = asyncio.run(fetch(session))
    except SedeError as exc:
        _CONSOLE.print(f"[red]notifications fetch failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(snapshot.model_dump(mode="json"), indent=2, default=str, ensure_ascii=False))
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
