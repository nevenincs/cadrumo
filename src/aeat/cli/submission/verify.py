"""``aeat submission verify`` — re-parse an exported fichero-BOE file.

EPIC #305 wave 95 (wave 97 refactor). The "verify" pillar of Kent's
produce -> verify -> export journey: he exports a filing, uploads it
to AEAT, and wants to confirm locally that the bytes he uploaded
decode back to the casilla values he intended. This command reads a
``.{modelo}`` file off disk, dispatches to the matching deserialiser,
and pretty-prints headers + non-zero casillas to the console.

Wave 97 lets the command auto-detect modelo + ejercicio from the
standard ``{NIF}{YYYY}{PERIODO}.{modelo}`` filename emitted by
``aeat submission export`` — the flags ``--modelo`` and
``--ejercicio`` remain available as overrides for files with
non-standard names.

The command is strictly read-only: it never mutates the file, talks
to the AEAT portal, or modifies any persisted state. If decoding
fails (wrong length, corrupt envelope markers, encoding mismatch),
the original exception surfaces with an exit code of 2 so Kent can
see what went wrong.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ...submission._formats._deserialise import (
    ParsedEnvelope,
    ParsedRecord,
    deserialise,
    deserialise_envelope,
)
from ._schema_registry import SCHEMA_REGISTRY

_CONSOLE = Console()

#: Standard filename pattern: 9-char NIF + 4-digit YYYY + 2-char PERIODO + ``.{modelo}``.
#: PERIODO is either ``[1-4]T`` (quarterly) or ``0[1-9]|1[0-2]`` (monthly).
_FILENAME_RE = re.compile(
    r"^(?P<nif>[A-Z0-9]{9})(?P<ejercicio>\d{4})(?P<periodo>[1-4]T|0[1-9]|1[0-2])\.(?P<modelo>\d{3})$"
)


def _infer_modelo_ejercicio(file_path: Path) -> tuple[str | None, str | None]:
    """Parse the filename for a ``{NIF}{YYYY}{PERIODO}.{modelo}`` pattern.

    Returns ``(modelo, ejercicio)`` or ``(None, None)`` if the name
    doesn't match; callers then require the explicit CLI overrides.
    """
    m = _FILENAME_RE.match(file_path.name)
    if m is None:
        return None, None
    return m.group("modelo"), m.group("ejercicio")


def verify_cmd(
    file_path: Path = typer.Argument(
        ..., exists=True, readable=True, help="Path to a fichero-BOE file written by ``aeat submission export``."
    ),
    modelo: str | None = typer.Option(
        None, "--modelo", "-m", help="Modelo code (e.g. ``130``, ``303``). Auto-detected from the filename if omitted."
    ),
    ejercicio: str | None = typer.Option(
        None, "--ejercicio", "-e", help="Filing year (e.g. ``2024``). Auto-detected from the filename if omitted."
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit a machine-readable JSON document instead of the rich-formatted tables.",
    ),
) -> None:
    """Re-parse an exported fichero-BOE file and pretty-print its contents.

    Raises :class:`typer.Exit(code=2)` on unsupported modelos, on a
    filename that can't be auto-parsed when ``--modelo``/``--ejercicio``
    are absent, or when the payload fails to decode against the
    selected schema.
    """
    if modelo is None or ejercicio is None:
        inferred_modelo, inferred_ejercicio = _infer_modelo_ejercicio(file_path)
        modelo = modelo or inferred_modelo
        ejercicio = ejercicio or inferred_ejercicio
    if modelo is None or ejercicio is None:
        _CONSOLE.print(
            f"[red]verify FAILED:[/red] cannot infer modelo/ejercicio from filename {file_path.name!r}. "
            f"Pass --modelo and --ejercicio explicitly."
        )
        raise typer.Exit(code=2)

    key = (modelo, ejercicio)
    entry = SCHEMA_REGISTRY.get(key)
    if entry is None:
        _CONSOLE.print(
            f"[red]verify UNSUPPORTED:[/red] modelo {modelo} ejercicio {ejercicio} "
            f"has no fichero-BOE schema. Available: {sorted(SCHEMA_REGISTRY.keys())}"
        )
        raise typer.Exit(code=2)

    payload = file_path.read_bytes()
    # Strip the trailing CRLF so the parser sees exactly RECORD_LENGTH
    # or ENVELOPE total_length bytes of content.
    content = payload[:-2] if payload.endswith(b"\r\n") else payload

    # Wave 135 pre-flight: catch a wrong-length payload with a Kent-facing
    # message naming the likely failure modes (wrong --modelo / --ejercicio
    # flags, truncated file, or a file from a different schema) before the
    # deserialiser surfaces a generic "content is N bytes but total_length
    # is M" error.
    if entry.kind == "record":
        expected = int(entry.module.RECORD_LENGTH)
    else:
        expected = sum(int(s.total_length) for s in entry.module.ENVELOPE)
    if len(content) != expected:
        msg = (
            f"verify FAILED: file is {len(content)} content byte(s) but "
            f"modelo={modelo} ejercicio={ejercicio} expects exactly {expected}. "
            "Likely causes: wrong --modelo / --ejercicio flag, a truncated file, "
            "or a file produced by a different schema version."
        )
        if as_json:
            typer.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": "PayloadLengthMismatch",
                        "error_message": msg,
                        "modelo": modelo,
                        "ejercicio": ejercicio,
                        "file": file_path.name,
                        "expected_bytes": expected,
                        "actual_bytes": len(content),
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            _CONSOLE.print(f"[red]{msg}[/red]")
        raise typer.Exit(code=2)

    try:
        if entry.kind == "record":
            parsed_record = deserialise(
                content,
                specs=entry.module.RECORD_SPECS,
                encoding=entry.module.ENCODING,
                total_length=entry.module.RECORD_LENGTH,
            )
            if as_json:
                _emit_record_json(parsed_record, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
            else:
                _print_record(parsed_record, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
        else:
            parsed_envelope = deserialise_envelope(
                content,
                segments=entry.module.ENVELOPE,
                encoding=entry.module.ENCODING,
            )
            if as_json:
                _emit_envelope_json(parsed_envelope, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
            else:
                _print_envelope(parsed_envelope, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
    except Exception as exc:
        if as_json:
            _emit_error_json(exc, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
        else:
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

    # Wave 103: surface the envelope-level header fields (NIF, PERIODO,
    # TIPO_DECLARACION, etc.) so Kent doesn't have to walk per-segment output.
    header_table = Table(title="headers (merged across segments, non-empty)", show_lines=False)
    header_table.add_column("field_id")
    header_table.add_column("value")
    for fid, value in sorted(parsed.merged_field_values.items(), key=lambda kv: kv[0]):
        rendered = str(value)
        # Skip empty-space placeholder filler so the table isn't overwhelmed
        # by 600-byte RESERVADO_PARA_LA_AEAT blanks.
        if rendered.strip() == "":
            continue
        header_table.add_row(fid, repr(value))
    _CONSOLE.print(header_table)

    casilla_table = Table(title="casillas (non-zero, merged across segments)", show_lines=False)
    casilla_table.add_column("casilla")
    casilla_table.add_column("value")
    for cid, value in sorted(parsed.merged_casilla_values.items(), key=lambda kv: kv[0]):
        if value != 0:
            casilla_table.add_row(cid, str(value))
    _CONSOLE.print(casilla_table)


def _jsonable(value: Any) -> Any:
    """Coerce Decimal / date / other non-JSON types to strings."""
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _emit_record_json(parsed: ParsedRecord, *, modelo: str, ejercicio: str, file_path: Path) -> None:
    """Print the machine-readable shape for a single-record parse."""
    payload = {
        "status": "ok",
        "kind": "record",
        "modelo": modelo,
        "ejercicio": ejercicio,
        "file": file_path.name,
        "raw_length": parsed.raw_length,
        "fields": {fid: _jsonable(val) for fid, val in parsed.field_values.items()},
        "casillas": {cid: str(val) for cid, val in parsed.casilla_values.items()},
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _emit_envelope_json(parsed: ParsedEnvelope, *, modelo: str, ejercicio: str, file_path: Path) -> None:
    """Print the machine-readable shape for a multi-segment envelope parse."""
    # Wave 103: drop empty-space filler so the JSON surface stays useful for
    # downstream scripts (the DP303DID reserved block is 617 bytes of ' ').
    fields = {fid: _jsonable(val) for fid, val in parsed.merged_field_values.items() if str(val).strip() != ""}
    payload = {
        "status": "ok",
        "kind": "envelope",
        "modelo": modelo,
        "ejercicio": ejercicio,
        "file": file_path.name,
        "segments": sorted(parsed.segments.keys()),
        "fields": fields,
        "casillas": {cid: str(val) for cid, val in parsed.merged_casilla_values.items()},
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _emit_error_json(exc: BaseException, *, modelo: str, ejercicio: str, file_path: Path) -> None:
    payload = {
        "status": "error",
        "modelo": modelo,
        "ejercicio": ejercicio,
        "file": file_path.name,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
