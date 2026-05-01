"""``aeat submission check-nif`` — standalone NIF / NIE / CIF validator.

EPIC #305 . Kent-facing pre-flight utility that runs the
AEAT check-letter algorithm on an identifier and reports the
result. Useful before he writes a draft JSON or invokes any other
CLI command: he can copy-paste a NIF / NIE / CIF from a document
and confirm the character sequence is sound without going through
the whole export flow.

Delegates to the already-shipped
:func:`aeat.core.identity.validate_spanish_tax_id`
so the rules stay single-sourced.

Exit codes:
- 0 — identifier is valid; canonical form printed.
- 2 — identifier is malformed or the check-letter is wrong.
"""

from __future__ import annotations

from typing import Literal

import typer
from rich.console import Console

from ....core.identity import validate_spanish_tax_id
from .._errors import CliRefusedBoundaryError, json_output_requested
from .._schemas import OutputSchema, emit_json_success, register_schema

_CONSOLE = Console()


@register_schema("submission check-nif")
class CheckNifJson(OutputSchema):
    """Schema for ``aeat submission check-nif --json``."""

    status: Literal["valid", "invalid"]
    input: str
    canonical: str | None = None
    kind: Literal["NIF", "NIE", "CIF"] | None = None
    error: str | None = None


def check_nif_cmd(
    tax_id: str = typer.Argument(..., help="Spanish NIF / NIE / CIF to validate."),
    as_json: bool = typer.Option(False, "--json", help="Emit a machine-readable JSON document instead of rich output."),
) -> None:
    """Validate a Spanish tax identifier against AEAT's check-letter rules."""
    emit_json = as_json or json_output_requested()
    try:
        canonical = validate_spanish_tax_id(tax_id)
    except ValueError as exc:
        if emit_json:
            raise CliRefusedBoundaryError(
                str(exc),
                context={"input": tax_id},
            ) from exc
        else:
            _CONSOLE.print(f"[red]check-nif INVALID:[/red] {tax_id!r} — {exc}")
        raise typer.Exit(code=2) from exc

    kind = _classify(canonical)
    if emit_json:
        emit_json_success(
            "submission check-nif",
            {"status": "valid", "input": tax_id, "canonical": canonical, "kind": kind},
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
