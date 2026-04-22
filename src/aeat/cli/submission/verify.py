"""``aeat submission verify`` — re-parse an exported fichero-BOE file.

EPIC #305 wave 95. The "verify" pillar of Kent's produce -> verify ->
export journey: he exports a filing, uploads it to AEAT, and wants
to confirm locally that the bytes he uploaded decode back to the
casilla values he intended. This command reads a ``.{modelo}`` file
off disk, dispatches to the matching deserialiser, and pretty-prints
headers + non-zero casillas to the console.

The command is strictly read-only: it never mutates the file, talks
to the AEAT portal, or modifies any persisted state. If decoding
fails (wrong length, corrupt envelope markers, encoding mismatch),
the original exception surfaces with an exit code of 2 so Kent can
see what went wrong.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ...submission._formats._deserialise import (
    ParsedEnvelope,
    ParsedRecord,
    deserialise,
    deserialise_envelope,
)
from .export import _SCHEMA_REGISTRY

_CONSOLE = Console()


def verify_cmd(
    file_path: Path = typer.Argument(
        ..., exists=True, readable=True, help="Path to a fichero-BOE file written by ``aeat submission export``."
    ),
    modelo: str = typer.Option(..., "--modelo", "-m", help="Modelo code, e.g. ``130`` or ``303``."),
    ejercicio: str = typer.Option(..., "--ejercicio", "-e", help="Filing year, e.g. ``2024``."),
) -> None:
    """Re-parse an exported fichero-BOE file and pretty-print its contents.

    Raises :class:`typer.Exit(code=2)` on unsupported modelos or when
    the payload fails to decode against the selected schema.
    """
    key = (modelo, ejercicio)
    entry = _SCHEMA_REGISTRY.get(key)
    if entry is None:
        _CONSOLE.print(
            f"[red]verify UNSUPPORTED:[/red] modelo {modelo} ejercicio {ejercicio} "
            f"has no fichero-BOE schema. Available: {sorted(_SCHEMA_REGISTRY.keys())}"
        )
        raise typer.Exit(code=2)

    payload = file_path.read_bytes()
    # Strip the trailing CRLF so the parser sees exactly RECORD_LENGTH
    # or ENVELOPE total_length bytes of content.
    content = payload[:-2] if payload.endswith(b"\r\n") else payload

    try:
        if entry.kind == "record":
            parsed = deserialise(
                content,
                specs=entry.module._RECORD_SPECS,
                encoding=entry.module.ENCODING,
                total_length=entry.module.RECORD_LENGTH,
            )
            _print_record(parsed, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
        else:
            parsed = deserialise_envelope(
                content,
                segments=entry.module.ENVELOPE,
                encoding=entry.module.ENCODING,
            )
            _print_envelope(parsed, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
    except Exception as exc:
        _CONSOLE.print(f"[red]verify FAILED:[/red] {type(exc).__name__}: {exc}")
        raise typer.Exit(code=2) from exc


def _print_record(parsed: ParsedRecord, *, modelo: str, ejercicio: str, file_path: Path) -> None:
    """Render a single-record parse (Modelo 130 shape)."""
    _CONSOLE.print(f"[green]verify OK[/green] modelo={modelo} ejercicio={ejercicio} file={file_path.name}")
    _CONSOLE.print(f"raw_length={parsed.raw_length}")

    table = Table(title="headers", show_lines=False)
    table.add_column("field_id")
    table.add_column("value")
    for field_id, value in parsed.field_values.items():
        table.add_row(field_id, repr(value))
    _CONSOLE.print(table)

    casilla_table = Table(title="casillas (non-zero)", show_lines=False)
    casilla_table.add_column("casilla")
    casilla_table.add_column("value")
    for cid, value in sorted(parsed.casilla_values.items(), key=lambda kv: kv[0]):
        if value != 0:
            casilla_table.add_row(cid, str(value))
    _CONSOLE.print(casilla_table)


def _print_envelope(parsed: ParsedEnvelope, *, modelo: str, ejercicio: str, file_path: Path) -> None:
    """Render a multi-segment envelope parse (Modelo 303 shape)."""
    _CONSOLE.print(f"[green]verify OK[/green] modelo={modelo} ejercicio={ejercicio} file={file_path.name}")
    _CONSOLE.print(f"segments={len(parsed.segments)}")

    casilla_table = Table(title="casillas (non-zero, merged across segments)", show_lines=False)
    casilla_table.add_column("casilla")
    casilla_table.add_column("value")
    for cid, value in sorted(parsed.merged_casilla_values.items(), key=lambda kv: kv[0]):
        if value != 0:
            casilla_table.add_row(cid, str(value))
    _CONSOLE.print(casilla_table)
