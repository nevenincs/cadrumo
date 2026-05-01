"""``aeat submission schemas`` — list every ``(modelo, ejercicio)`` the CLI can export.

The discovery surface: rather than trial-and-error with
``aeat submission export --help`` and hoping a modelo is wired, an
operator can run ``aeat submission schemas`` to see the complete
registry plus per-schema size, encoding, and dispatch-kind metadata
sourced from :data:`._schema_registry.SCHEMA_REGISTRY`.

Strictly read-only — no filesystem or network access beyond the in-
process registry lookup.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from .._errors import json_output_requested
from .._schemas import OutputRootSchema, OutputSchema, emit_json_success, register_schema
from ._schema_registry import SCHEMA_REGISTRY, SchemaEntry

_CONSOLE = Console()


class SubmissionSchemaRow(OutputSchema):
    """One row from ``aeat submission schemas --json``.

    Attributes:
        modelo: Modelo code.
        ejercicio: Filing year.
        kind: ``"record"`` (single fixed-width payload) or ``"envelope"``
            (multi-segment XML-wrapped payload).
        encoding: The schema's character encoding (e.g. ``"latin-1"``).
        bytes: Total payload length in bytes (excluding the ``\\r\\n``
            terminator).
        required_header_fields: Count of required header fields the
            serialiser enforces.
    """

    modelo: str
    ejercicio: str
    kind: str
    encoding: str
    bytes: int
    required_header_fields: int


@register_schema("submission schemas")
class SubmissionSchemasJson(OutputRootSchema[list[SubmissionSchemaRow]]):
    """Top-level JSON wrapper schema for ``aeat submission schemas --json``.

    Wraps a list of :class:`SubmissionSchemaRow`.
    """


def _schema_row(key: tuple[str, str], entry: SchemaEntry) -> dict[str, object]:
    """Compute the public description of one registry entry.

    Args:
        key: ``(modelo, ejercicio)`` registry key.
        entry: The matching :class:`._schema_registry.SchemaEntry`.

    Returns:
        A mapping shaped like :class:`SubmissionSchemaRow` (extra keys
        forbidden).
    """
    modelo, ejercicio = key
    module = entry.module
    total = int(module.RECORD_LENGTH) if entry.kind == "record" else sum(int(s.total_length) for s in module.ENVELOPE)
    return {
        "modelo": modelo,
        "ejercicio": ejercicio,
        "kind": entry.kind,
        "encoding": str(module.ENCODING),
        "bytes": total,
        "required_header_fields": len(module.REQUIRED_HEADER_FIELDS),
    }


def schemas_cmd(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit a machine-readable JSON array instead of the rich-formatted table.",
    ),
) -> None:
    """List every fichero-BOE schema the CLI can produce and verify.

    Args:
        as_json: When ``True``, emit a machine-readable JSON array
            instead of the rich-formatted table.
    """
    rows = [_schema_row(key, entry) for key, entry in sorted(SCHEMA_REGISTRY.items())]

    if as_json or json_output_requested():
        emit_json_success("submission schemas", rows, sort_keys=True)
        return

    table = Table(title="aeat submission schemas", show_lines=False)
    table.add_column("modelo")
    table.add_column("ejercicio")
    table.add_column("kind")
    table.add_column("encoding")
    table.add_column("bytes", justify="right")
    table.add_column("required headers", justify="right")
    for row in rows:
        table.add_row(
            str(row["modelo"]),
            str(row["ejercicio"]),
            str(row["kind"]),
            str(row["encoding"]),
            str(row["bytes"]),
            str(row["required_header_fields"]),
        )
    _CONSOLE.print(table)
    _CONSOLE.print(
        f"[green]{len(rows)} schema(s) registered.[/green] "
        "Use `aeat submission export <draft>` to emit, "
        "`aeat submission verify <file>` to re-parse."
    )
