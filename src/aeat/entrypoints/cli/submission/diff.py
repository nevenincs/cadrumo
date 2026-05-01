"""``aeat submission diff`` — compare two fichero-BOE files.

EPIC #305 . Kent's verification journey extends to the
comparison case: he exports filing A, later re-downloads his AEAT
"declaración presentada" receipt as filing B, and wants to confirm
the two match — or if they don't, exactly which casilla diverged.

The command is strictly read-only. It parses both files through the
same :mod:`_schema_registry` dispatch used by
:mod:`export` / :mod:`verify`, diffs byte-by-byte as a fast-path
guard, then diffs field-by-field and casilla-by-casilla so the
console output names the semantic delta (not just "files differ").

Exit codes:
- 0 — files are byte-identical.
- 1 — files parse cleanly but show at least one semantic difference.
- 2 — unsupported modelo, unparseable filename, or decoder failure.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import typer
from pydantic import Field
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
from ._schema_registry import SCHEMA_REGISTRY, SchemaEntry, validate_ejercicio_flag, validate_modelo_flag
from .verify import _infer_modelo_ejercicio

_CONSOLE = Console()


class SubmissionDiffDelta(OutputSchema):
    """One field or casilla delta from ``aeat submission diff --json``."""

    casilla: str | None = None
    field_id: str | None = None
    a: str
    b: str


class SubmissionDiffPayload(OutputSchema):
    """Schema for ``aeat submission diff --json`` payload objects."""

    status: Literal["identical", "mismatch", "bytes-differ-no-semantic-delta", "unsupported", "error"]
    modelo: str | None = None
    ejercicio: str | None = None
    bytes: int | None = None
    file_a: str | None = None
    file_b: str | None = None
    casilla_deltas: list[SubmissionDiffDelta] = Field(default_factory=list)
    field_deltas: list[SubmissionDiffDelta] = Field(default_factory=list)
    available: list[list[str]] | None = None
    error_type: str | None = None
    error_message: str | None = None
    which_file: str | None = None
    expected_bytes: int | None = None
    actual_bytes: int | None = None


@register_schema("submission diff")
class SubmissionDiffJson(OutputRootSchema[SubmissionDiffPayload]):
    """Schema for ``aeat submission diff --json``."""


def diff_cmd(
    file_a: Path = typer.Argument(..., exists=True, readable=True, help="First fichero-BOE file."),
    file_b: Path = typer.Argument(..., exists=True, readable=True, help="Second fichero-BOE file."),
    modelo: str | None = typer.Option(
        None,
        "--modelo",
        "-m",
        help="Modelo code; auto-detected from FILE_A's filename if omitted.",
        callback=validate_modelo_flag,
    ),
    ejercicio: str | None = typer.Option(
        None,
        "--ejercicio",
        "-e",
        help="Filing year; auto-detected from FILE_A's filename if omitted.",
        callback=validate_ejercicio_flag,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit a machine-readable JSON document instead of the rich-formatted tables.",
    ),
) -> None:
    """Diff two fichero-BOE files and report byte + semantic deltas.

    The schema is inferred from FILE_A's filename when the CLI flags
    are omitted; FILE_B is assumed to share the same schema and any
    shape mismatch surfaces at the decoder boundary with exit 2.
    """
    emit_json = as_json or json_output_requested()
    if modelo is None or ejercicio is None:
        inferred_modelo, inferred_ejercicio = _infer_modelo_ejercicio(file_a)
        modelo = modelo or inferred_modelo
        ejercicio = ejercicio or inferred_ejercicio
    if modelo is None or ejercicio is None:
        if emit_json:
            raise CliRefusedBoundaryError(
                (
                    f"Cannot infer modelo/ejercicio from filename {file_a.name!r}. "
                    "Pass --modelo and --ejercicio explicitly."
                ),
                context={"file_a": file_a.name},
            )
        else:
            _CONSOLE.print(
                f"[red]diff FAILED:[/red] cannot infer modelo/ejercicio from filename "
                f"{file_a.name!r}. Pass --modelo and --ejercicio explicitly."
            )
        raise typer.Exit(code=2)

    entry = SCHEMA_REGISTRY.get((modelo, ejercicio))
    if entry is None:
        if emit_json:
            raise CliRefusedBoundaryError(
                f"modelo {modelo} ejercicio {ejercicio} has no fichero-BOE schema.",
                context={
                    "modelo": modelo,
                    "ejercicio": ejercicio,
                    "available": sorted([[m, e] for m, e in SCHEMA_REGISTRY]),
                },
            )
        else:
            _CONSOLE.print(
                f"[red]diff UNSUPPORTED:[/red] modelo {modelo} ejercicio {ejercicio} "
                f"has no fichero-BOE schema. Available: {sorted(SCHEMA_REGISTRY.keys())}"
            )
        raise typer.Exit(code=2)

    payload_a = file_a.read_bytes()
    payload_b = file_b.read_bytes()

    # per-file payload-length pre-flight with Kent-facing message.
    expected = (
        int(entry.module.RECORD_LENGTH)
        if entry.kind == "record"
        else sum(int(s.total_length) for s in entry.module.ENVELOPE)
    )
    for label, file_path, payload in (("a", file_a, payload_a), ("b", file_b, payload_b)):
        content = payload[:-2] if payload.endswith(b"\r\n") else payload
        if len(content) != expected:
            msg = (
                f"diff FAILED: file_{label} ({file_path.name}) is {len(content)} content "
                f"byte(s) but modelo={modelo} ejercicio={ejercicio} expects exactly "
                f"{expected}. Wrong --modelo/--ejercicio flag or corrupt file?"
            )
            if emit_json:
                raise CliRefusedBoundaryError(
                    msg,
                    context={
                        "modelo": modelo,
                        "ejercicio": ejercicio,
                        "which_file": f"file_{label}",
                        "expected_bytes": expected,
                        "actual_bytes": len(content),
                    },
                )
            else:
                _CONSOLE.print(f"[red]{msg}[/red]")
            raise typer.Exit(code=2)

    if payload_a == payload_b:
        if emit_json:
            emit_json_success(
                "submission diff",
                {
                    "status": "identical",
                    "modelo": modelo,
                    "ejercicio": ejercicio,
                    "bytes": len(payload_a),
                    "file_a": file_a.name,
                    "file_b": file_b.name,
                    "casilla_deltas": [],
                    "field_deltas": [],
                },
            )
        else:
            _CONSOLE.print(
                f"[green]diff OK[/green] files are byte-identical "
                f"({len(payload_a)} bytes, modelo={modelo}, ejercicio={ejercicio})."
            )
        return

    try:
        parsed_a = _parse(payload_a, entry=entry)
        parsed_b = _parse(payload_b, entry=entry)
    except Exception as exc:
        if emit_json:
            raise CliRefusedBoundaryError(
                f"{type(exc).__name__}: {exc}",
                context={
                    "error_type": type(exc).__name__,
                    "modelo": modelo,
                    "ejercicio": ejercicio,
                },
            ) from exc
        else:
            _CONSOLE.print(f"[red]diff FAILED:[/red] {type(exc).__name__}: {exc}")
        raise typer.Exit(code=2) from exc

    if emit_json:
        diffs_found = _emit_diff_json(
            parsed_a,
            parsed_b,
            file_a=file_a,
            file_b=file_b,
            modelo=modelo,
            ejercicio=ejercicio,
        )
    else:
        diffs_found = _report_semantic_diff(
            parsed_a,
            parsed_b,
            file_a=file_a,
            file_b=file_b,
            modelo=modelo,
            ejercicio=ejercicio,
        )
    if diffs_found:
        raise typer.Exit(code=1)


def _parse(payload: bytes, *, entry: SchemaEntry) -> ParsedRecord | ParsedEnvelope:
    content = payload[:-2] if payload.endswith(b"\r\n") else payload
    if entry.kind == "record":
        return deserialise(
            content,
            specs=entry.module.RECORD_SPECS,
            encoding=entry.module.ENCODING,
            total_length=entry.module.RECORD_LENGTH,
        )
    return deserialise_envelope(
        content,
        segments=entry.module.ENVELOPE,
        encoding=entry.module.ENCODING,
    )


def _report_semantic_diff(
    parsed_a: ParsedRecord | ParsedEnvelope,
    parsed_b: ParsedRecord | ParsedEnvelope,
    *,
    file_a: Path,
    file_b: Path,
    modelo: str,
    ejercicio: str,
) -> bool:
    """Pretty-print the per-field and per-casilla deltas. Returns True
    when at least one difference was reported."""
    _CONSOLE.print(
        f"[yellow]diff MISMATCH[/yellow] modelo={modelo} ejercicio={ejercicio} a={file_a.name} b={file_b.name}"
    )

    casillas_a = _casillas_of(parsed_a)
    casillas_b = _casillas_of(parsed_b)
    casilla_deltas = _dict_diff(casillas_a, casillas_b)

    if casilla_deltas:
        table = Table(title="casilla deltas", show_lines=False)
        table.add_column("casilla")
        table.add_column("a")
        table.add_column("b")
        for cid, a_val, b_val in casilla_deltas:
            table.add_row(cid, _render(a_val), _render(b_val))
        _CONSOLE.print(table)

    field_deltas = _dict_diff(_fields_of(parsed_a), _fields_of(parsed_b))
    if field_deltas:
        table = Table(title="header / field deltas", show_lines=False)
        table.add_column("field_id")
        table.add_column("a")
        table.add_column("b")
        for fid, a_val, b_val in field_deltas:
            table.add_row(fid, _render(a_val), _render(b_val))
        _CONSOLE.print(table)

    if not casilla_deltas and not field_deltas:
        _CONSOLE.print(
            "[yellow]bytes differ but every decoded casilla + field is equal — "
            "encoding artefact or filler-slot difference.[/yellow]"
        )

    return bool(casilla_deltas or field_deltas)


def _casillas_of(parsed: ParsedRecord | ParsedEnvelope) -> Mapping[str, object]:
    if isinstance(parsed, ParsedEnvelope):
        return parsed.merged_casilla_values
    return parsed.casilla_values


def _fields_of(parsed: ParsedRecord | ParsedEnvelope) -> Mapping[str, object]:
    if isinstance(parsed, ParsedEnvelope):
        return parsed.merged_field_values
    return parsed.field_values


def _dict_diff(a: Mapping[str, object], b: Mapping[str, object]) -> list[tuple[str, object, object]]:
    keys = set(a) | set(b)
    out: list[tuple[str, object, object]] = []
    for k in sorted(keys):
        va = a.get(k)
        vb = b.get(k)
        if va != vb:
            out.append((k, va, vb))
    return out


def _render(value: object) -> str:
    if value is None:
        return "<missing>"
    return str(value)


def _emit_diff_json(
    parsed_a: ParsedRecord | ParsedEnvelope,
    parsed_b: ParsedRecord | ParsedEnvelope,
    *,
    file_a: Path,
    file_b: Path,
    modelo: str,
    ejercicio: str,
) -> bool:
    """Emit the semantic-diff machine-readable shape. Returns True when at
    least one delta was reported."""
    casilla_deltas = _dict_diff(_casillas_of(parsed_a), _casillas_of(parsed_b))
    field_deltas = _dict_diff(_fields_of(parsed_a), _fields_of(parsed_b))

    payload = {
        "status": "mismatch" if (casilla_deltas or field_deltas) else "bytes-differ-no-semantic-delta",
        "modelo": modelo,
        "ejercicio": ejercicio,
        "file_a": file_a.name,
        "file_b": file_b.name,
        "casilla_deltas": [
            {"casilla": cid, "a": _render(a_val), "b": _render(b_val)} for cid, a_val, b_val in casilla_deltas
        ],
        "field_deltas": [
            {"field_id": fid, "a": _render(a_val), "b": _render(b_val)} for fid, a_val, b_val in field_deltas
        ],
    }
    emit_json_success("submission diff", payload, sort_keys=True)
    return bool(casilla_deltas or field_deltas)
