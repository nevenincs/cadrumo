"""``aeat submission verify`` -- re-parse an exported fichero-BOE file.

The "verify" pillar of the produce -> verify -> export journey: the
operator exports a filing, uploads it to AEAT, and wants to confirm
locally that the bytes uploaded decode back to the casilla values
they intended. This command reads a ``.{modelo}`` file off disk,
dispatches to the matching deserialiser, and pretty-prints headers
plus non-zero casillas to the console.

The command auto-detects modelo and ejercicio from the standard
``{NIF}{YYYY}{PERIODO}.{modelo}`` filename emitted by ``aeat
submission export``. The flags ``--modelo`` and ``--ejercicio``
remain available as overrides for files with non-standard names.

The command is strictly read-only: it never mutates the file, talks
to the AEAT portal, or modifies any persisted state. If decoding
fails (wrong length, corrupt envelope markers, encoding mismatch),
the original exception surfaces with an exit code of 2.

See also:
    :mod:`aeat.entrypoints.cli.submission._schema_registry` for the
    registry consulted at dispatch time and
    :mod:`aeat.adapters.outbound.aeat.export._formats._deserialise`
    for the underlying parsers.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import typer
from rich.console import Console
from rich.table import Table

from ....adapters.outbound.aeat.export._formats._deserialise import (
    ParsedEnvelope,
    ParsedRecord,
    deserialise,
    deserialise_envelope,
)
from .._errors import CliRefusedBoundaryError, json_output_requested
from .._schemas import OutputRootSchema, OutputSchema, emit_json_success, register_schema
from ._schema_registry import SCHEMA_REGISTRY, validate_ejercicio_flag, validate_modelo_flag

_CONSOLE = Console()

_FILENAME_RE = re.compile(
    r"^(?P<nif>[A-Z0-9]{9})(?P<ejercicio>\d{4})(?P<periodo>[1-4]T|0[1-9]|1[0-2])\.(?P<modelo>\d{3})$"
)
"""Standard fichero-BOE filename pattern.

Matches a 9-character NIF, a 4-digit ``YYYY``, a 2-character periodo
(quarterly ``[1-4]T`` or monthly ``0[1-9]|1[0-2]``), and a 3-digit
``.{modelo}`` extension.
"""


class SubmissionVerifyOkRecord(OutputSchema):
    """Successful record payload for ``aeat submission verify --json``.

    Attributes:
        status: Always ``"ok"``.
        kind: Always ``"record"`` -- single fixed-width record schema.
        modelo: The 3-digit modelo code (e.g. ``"130"``).
        ejercicio: The 4-digit fiscal year (e.g. ``"2024"``).
        file: Filename of the parsed payload.
        raw_length: Total bytes parsed from the payload.
        fields: Header field values keyed by field id.
        casillas: Casilla values keyed by casilla code.
    """

    status: Literal["ok"]
    kind: Literal["record"]
    modelo: str
    ejercicio: str
    file: str
    raw_length: int
    fields: dict[str, str]
    casillas: dict[str, str]


class SubmissionVerifyOkEnvelope(OutputSchema):
    """Successful envelope payload for ``aeat submission verify --json``.

    Attributes:
        status: Always ``"ok"``.
        kind: Always ``"envelope"`` -- multi-segment schema.
        modelo: The 3-digit modelo code (e.g. ``"303"``).
        ejercicio: The 4-digit fiscal year.
        file: Filename of the parsed payload.
        segments: Sorted list of envelope segment ids encountered.
        fields: Merged non-empty header field values across segments.
        casillas: Merged casilla values keyed by casilla code.
    """

    status: Literal["ok"]
    kind: Literal["envelope"]
    modelo: str
    ejercicio: str
    file: str
    segments: list[str]
    fields: dict[str, str]
    casillas: dict[str, str]


class SubmissionVerifyError(OutputSchema):
    """Error payload for ``aeat submission verify --json``.

    Attributes:
        status: Always ``"error"``.
        modelo: The 3-digit modelo code that failed to verify.
        ejercicio: The 4-digit fiscal year.
        file: Filename of the offending payload.
        error_type: Class name of the originating exception.
        error_message: Operator-facing description of the failure.
        expected_bytes: Expected payload length when the failure is a
            length mismatch; ``None`` otherwise.
        actual_bytes: Observed payload length when known.
    """

    status: Literal["error"]
    modelo: str
    ejercicio: str
    file: str
    error_type: str
    error_message: str
    expected_bytes: int | None = None
    actual_bytes: int | None = None


@register_schema("submission verify")
class SubmissionVerifyJson(
    OutputRootSchema[SubmissionVerifyOkRecord | SubmissionVerifyOkEnvelope | SubmissionVerifyError]
):
    """Discriminated-union root schema for ``aeat submission verify --json``."""


def _infer_modelo_ejercicio(file_path: Path) -> tuple[str | None, str | None]:
    """Parse a filename for the ``{NIF}{YYYY}{PERIODO}.{modelo}`` pattern.

    Args:
        file_path: Path whose ``name`` is matched against
            :data:`_FILENAME_RE`.

    Returns:
        ``(modelo, ejercicio)`` if the name matches, otherwise
        ``(None, None)``. Callers then require the explicit
        ``--modelo`` / ``--ejercicio`` CLI overrides.
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
        None,
        "--modelo",
        "-m",
        help="Modelo code (e.g. ``130``, ``303``). Auto-detected from the filename if omitted.",
        callback=validate_modelo_flag,
    ),
    ejercicio: str | None = typer.Option(
        None,
        "--ejercicio",
        "-e",
        help="Filing year (e.g. ``2024``). Auto-detected from the filename if omitted.",
        callback=validate_ejercicio_flag,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit a machine-readable JSON document instead of the rich-formatted tables.",
    ),
) -> None:
    """Re-parse an exported fichero-BOE file and pretty-print its contents.

    Args:
        file_path: Path to a fichero-BOE file written by ``aeat
            submission export``.
        modelo: Optional 3-digit modelo code; auto-detected from the
            filename when omitted.
        ejercicio: Optional 4-digit fiscal year; auto-detected from
            the filename when omitted.
        as_json: When ``True``, emit a JSON document instead of the
            rich-formatted tables.

    Raises:
        typer.Exit: With code ``2`` on unsupported modelos, on a
            filename that cannot be auto-parsed when ``--modelo`` or
            ``--ejercicio`` are absent, or when the payload fails to
            decode against the selected schema.
        :exc:`aeat.entrypoints.cli._errors.CliRefusedBoundaryError`:
            In JSON mode, wrapping the failure context for the
            structured error envelope.
    """
    emit_json = as_json or json_output_requested()
    if modelo is None or ejercicio is None:
        inferred_modelo, inferred_ejercicio = _infer_modelo_ejercicio(file_path)
        modelo = modelo or inferred_modelo
        ejercicio = ejercicio or inferred_ejercicio
    if modelo is None or ejercicio is None:
        message = (
            f"cannot infer modelo/ejercicio from filename {file_path.name!r}. Pass --modelo and --ejercicio explicitly."
        )
        if emit_json:
            raise CliRefusedBoundaryError(message, context={"file": file_path.name})
        _CONSOLE.print(f"[red]verify FAILED:[/red] {message}")
        raise typer.Exit(code=2)

    key = (modelo, ejercicio)
    entry = SCHEMA_REGISTRY.get(key)
    if entry is None:
        message = (
            f"modelo {modelo} ejercicio {ejercicio} has no fichero-BOE schema. "
            f"Available: {sorted(SCHEMA_REGISTRY.keys())}"
        )
        if emit_json:
            raise CliRefusedBoundaryError(message, context={"modelo": modelo, "ejercicio": ejercicio})
        _CONSOLE.print(f"[red]verify UNSUPPORTED:[/red] {message}")
        raise typer.Exit(code=2)

    payload = file_path.read_bytes()
    # Strip the trailing CRLF so the parser sees exactly RECORD_LENGTH
    # or ENVELOPE total_length bytes of content.
    content = payload[:-2] if payload.endswith(b"\r\n") else payload

    # pre-flight: catch a wrong-length payload with a Kent-facing
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
        if emit_json:
            raise CliRefusedBoundaryError(
                msg,
                context={
                    "modelo": modelo,
                    "ejercicio": ejercicio,
                    "file": file_path.name,
                    "expected_bytes": expected,
                    "actual_bytes": len(content),
                },
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
            if emit_json:
                _emit_record_json(parsed_record, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
            else:
                _print_record(parsed_record, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
        else:
            parsed_envelope = deserialise_envelope(
                content,
                segments=entry.module.ENVELOPE,
                encoding=entry.module.ENCODING,
            )
            if emit_json:
                _emit_envelope_json(parsed_envelope, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
            else:
                _print_envelope(parsed_envelope, modelo=modelo, ejercicio=ejercicio, file_path=file_path)
    except Exception as exc:
        if emit_json:
            raise CliRefusedBoundaryError(
                f"{type(exc).__name__}: {exc}",
                context={
                    "modelo": modelo,
                    "ejercicio": ejercicio,
                    "file": file_path.name,
                    "error_type": type(exc).__name__,
                },
            ) from exc
        else:
            _CONSOLE.print(f"[red]verify FAILED:[/red] {type(exc).__name__}: {exc}")
        raise typer.Exit(code=2) from exc


def _print_record(parsed: ParsedRecord, *, modelo: str, ejercicio: str, file_path: Path) -> None:
    """Render a single-record parse (Modelo 130 shape) to the console."""
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
    """Render a multi-segment envelope parse (Modelo 303 shape) to the console."""
    _CONSOLE.print(f"[green]verify OK[/green] modelo={modelo} ejercicio={ejercicio} file={file_path.name}")
    _CONSOLE.print(f"segments={len(parsed.segments)}")

    # surface the envelope-level header fields (NIF, PERIODO,
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
    """Coerce ``Decimal`` / date / other non-JSON-native types to strings."""
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _emit_record_json(parsed: ParsedRecord, *, modelo: str, ejercicio: str, file_path: Path) -> None:
    """Emit the machine-readable JSON document for a single-record parse."""
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
    emit_json_success("submission verify", payload, sort_keys=True)


def _emit_envelope_json(parsed: ParsedEnvelope, *, modelo: str, ejercicio: str, file_path: Path) -> None:
    """Emit the machine-readable JSON document for a multi-segment envelope parse."""
    # drop empty-space filler so the JSON surface stays useful for
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
    emit_json_success("submission verify", payload, sort_keys=True)
