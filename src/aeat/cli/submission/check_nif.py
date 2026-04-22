"""``aeat submission check-nif`` — standalone NIF / NIE / CIF validator.

EPIC #305 wave 107. Kent-facing pre-flight utility that runs the
AEAT check-letter algorithm on an identifier and reports the
result. Useful before he writes a draft JSON or invokes any other
CLI command: he can copy-paste a NIF / NIE / CIF from a document
and confirm the character sequence is sound without going through
the whole export flow.

Delegates to the already-shipped
:func:`aeat.financial.invoices._validators.validate_spanish_tax_id`
so the rules stay single-sourced.

Exit codes:
- 0 — identifier is valid; canonical form printed.
- 2 — identifier is malformed or the check-letter is wrong.
"""

from __future__ import annotations

import json

import typer
from rich.console import Console

from ...financial.invoices._validators import validate_spanish_tax_id

_CONSOLE = Console()


def check_nif_cmd(
    tax_id: str = typer.Argument(..., help="Spanish NIF / NIE / CIF to validate."),
    as_json: bool = typer.Option(False, "--json", help="Emit a machine-readable JSON document instead of rich output."),
) -> None:
    """Validate a Spanish tax identifier against AEAT's check-letter rules."""
    try:
        canonical = validate_spanish_tax_id(tax_id)
    except ValueError as exc:
        if as_json:
            typer.echo(
                json.dumps(
                    {"status": "invalid", "input": tax_id, "error": str(exc)},
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            _CONSOLE.print(f"[red]check-nif INVALID:[/red] {tax_id!r} — {exc}")
        raise typer.Exit(code=2) from exc

    kind = _classify(canonical)
    if as_json:
        typer.echo(
            json.dumps(
                {"status": "valid", "input": tax_id, "canonical": canonical, "kind": kind},
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    _CONSOLE.print(f"[green]check-nif OK[/green] {canonical} (kind={kind})")


def _classify(canonical: str) -> str:
    """Label the canonical identifier as NIF / NIE / CIF for the report."""
    leader = canonical[0]
    if leader.isdigit():
        return "NIF"
    if leader in {"X", "Y", "Z"}:
        return "NIE"
    return "CIF"
