"""``aeat submission check-nif`` — standalone NIF / NIE / CIF validator.

Operator-facing pre-flight utility that runs the AEAT check-letter
algorithm on an identifier and reports the result. Useful before
writing a draft JSON or invoking any other CLI command: an operator
can copy-paste a NIF / NIE / CIF from a document and confirm the
character sequence is sound without going through the whole export
flow.

Delegates to :func:`aeat.core.identity.validate_spanish_tax_id` so the
rules stay single-sourced.

Exit codes:

- ``0`` — identifier is valid; canonical form printed.
- ``2`` — identifier is malformed or the check-letter is wrong.
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
    """JSON output schema for ``aeat submission check-nif --json``.

    Attributes:
        status: ``"valid"`` when the identifier passes; ``"invalid"``
            otherwise.
        input: The original identifier as supplied by the operator.
        canonical: Canonical (upper-cased) form of the identifier when
            valid.
        kind: Inferred kind (``"NIF"``, ``"NIE"``, or ``"CIF"``) when
            valid.
        error: Human-readable failure description when invalid.
    """

    status: Literal["valid", "invalid"]
    input: str
    canonical: str | None = None
    kind: Literal["NIF", "NIE", "CIF"] | None = None
    error: str | None = None


def check_nif_cmd(
    tax_id: str = typer.Argument(..., help="Spanish NIF / NIE / CIF to validate."),
    as_json: bool = typer.Option(False, "--json", help="Emit a machine-readable JSON document instead of rich output."),
) -> None:
    """Validate a Spanish tax identifier against AEAT's check-letter rules.

    Args:
        tax_id: The identifier to validate.
        as_json: When ``True``, emit a machine-readable JSON document
            instead of rich console output.

    Raises:
        :exc:`aeat.entrypoints.cli._errors.CliRefusedBoundaryError`: When
            ``--json`` is active and the identifier is invalid.
        typer.Exit: With code ``2`` when the identifier is invalid in
            rich-output mode.
    """
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
    """Label the canonical identifier as ``NIF``, ``NIE``, or ``CIF``.

    Args:
        canonical: The upper-cased canonical identifier.

    Returns:
        ``"NIF"`` for digit-leading identifiers, ``"NIE"`` for
        ``X``/``Y``/``Z`` leaders, and ``"CIF"`` otherwise.
    """
    leader = canonical[0]
    if leader.isdigit():
        return "NIF"
    if leader in {"X", "Y", "Z"}:
        return "NIE"
    return "CIF"
