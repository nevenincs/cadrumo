"""``aeat submission schemas`` — list every (modelo, ejercicio) the CLI can export.

EPIC #305 wave 104. Kent's discovery surface: rather than trial-
and-error with ``aeat submission export --help`` and hoping his
modelo is wired, he can run ``aeat submission schemas`` to see the
complete registry plus per-schema size / encoding / dispatch-kind
metadata.

Strictly read-only — no filesystem or network access.
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from ._schema_registry import SCHEMA_REGISTRY, SchemaEntry

_CONSOLE = Console()


def _schema_row(key: tuple[str, str], entry: SchemaEntry) -> dict[str, object]:
    """Compute the public description of one registry entry."""
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
    """List every fichero-BOE schema the CLI can produce and verify."""
    rows = [_schema_row(key, entry) for key, entry in sorted(SCHEMA_REGISTRY.items())]

    if as_json:
        typer.echo(json.dumps(rows, indent=2, sort_keys=True))
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
