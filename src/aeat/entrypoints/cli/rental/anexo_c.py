"""``aeat rental anexo-c`` commands (#454).

Two commands:

  - ``compute``: derives the M100 Anexo C casillas (0061/0066/0072/
    0078/0085) for an ejercicio from the rental register and emits
    them as JSON.
  - ``verify``: cross-checks register-derived casillas against
    caller-supplied values and surfaces any discrepancy.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import typer

from ....domain.rental import (
    AnexoCAggregates,
    AnexoCMergeReport,
    RentalAmortizationLedgerRepository,
    RentalContractRepository,
    RentalExpenseRepository,
    RentalFincaRepository,
    RentalIncomeRepository,
    compute_anexo_c_aggregates,
    compute_or_passthrough,
)
from .._errors import json_output_requested
from .._schemas import OutputSchema, emit_json_success, register_schema
from ._helpers import open_session

app = typer.Typer(
    name="anexo-c",
    no_args_is_help=True,
    help="Cálculo y verificación de Anexo C M100 desde el registro (#454).",
)


@register_schema("rental anexo-c compute")
class AnexoCComputeJson(OutputSchema):
    aggregates: AnexoCAggregates


@register_schema("rental anexo-c verify")
class AnexoCVerifyJson(OutputSchema):
    report: AnexoCMergeReport


@app.command(name="compute", help="Calcular Anexo C M100 desde el registro para un ejercicio.")
def compute_cmd(period_year: int = typer.Option(..., "--year")) -> None:
    with open_session() as session:
        aggregates = compute_anexo_c_aggregates(
            period_year=period_year,
            finca_repo=RentalFincaRepository(session),
            contract_repo=RentalContractRepository(session),
            income_repo=RentalIncomeRepository(session),
            expense_repo=RentalExpenseRepository(session),
            ledger_repo=RentalAmortizationLedgerRepository(session),
        )
    if json_output_requested():
        emit_json_success(
            "rental anexo-c compute",
            AnexoCComputeJson(aggregates=aggregates),
            sort_keys=True,
        )
        return
    typer.echo(f"Period: {aggregates.period_year}")
    typer.echo(f"  0061 ingresos:        {aggregates.casilla_0061}")
    typer.echo(f"  0066 gastos:          {aggregates.casilla_0066}")
    typer.echo(f"  0072 amortizacion:    {aggregates.casilla_0072}")
    typer.echo(f"  0078 reduccion:       {aggregates.casilla_0078}")
    typer.echo(f"  0085 imputacion:      {aggregates.casilla_0085}")


@app.command(
    name="verify",
    help="Cotejar casillas suministradas vs registro (lee JSON con 0061..0085).",
)
def verify_cmd(
    period_year: int = typer.Option(..., "--year"),
    supplied: Path = typer.Option(
        ...,
        "--supplied",
        exists=True,
        readable=True,
        help="Archivo JSON con las casillas suministradas (claves 0061/0066/0072/0078/0085).",
    ),
) -> None:
    raw = json.loads(supplied.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter("supplied JSON must be a flat object of casilla -> amount")
    provided = {key: Decimal(str(value)) for key, value in raw.items()}
    with open_session() as session:
        report = compute_or_passthrough(
            period_year=period_year,
            provided_casillas=provided,
            finca_repo=RentalFincaRepository(session),
            contract_repo=RentalContractRepository(session),
            income_repo=RentalIncomeRepository(session),
            expense_repo=RentalExpenseRepository(session),
            ledger_repo=RentalAmortizationLedgerRepository(session),
        )
    if json_output_requested():
        emit_json_success("rental anexo-c verify", AnexoCVerifyJson(report=report), sort_keys=True)
        return
    if not report.register_used:
        typer.echo("Register not populated for this period; supplied casillas pass through.")
        return
    if not report.overridden:
        typer.echo("Supplied casillas match register-derived values for every casilla.")
        return
    typer.echo("Discrepancies between supplied and register-derived:")
    for casilla, (supplied_value, derived_value) in sorted(report.overridden.items()):
        typer.echo(f"  {casilla}: supplied={supplied_value} derived={derived_value}")


__all__ = ["app"]
