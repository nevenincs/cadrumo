"""``aeat rental income`` commands (#454)."""

from __future__ import annotations

from decimal import Decimal

import typer

from ...rental import (
    ContractNotFoundError,
    RentalContractRepository,
    RentalIncomeRecord,
    RentalIncomeRepository,
)
from .._errors import json_output_requested
from .._schemas import OutputRootSchema, OutputSchema, emit_json_success, register_schema
from ._helpers import open_session

app = typer.Typer(
    name="income",
    no_args_is_help=True,
    help="Registro de ingresos íntegros por contrato/ejercicio (#454).",
)


@register_schema("rental income record")
class IncomeRecordJson(OutputSchema):
    record: RentalIncomeRecord


@register_schema("rental income list")
class IncomeListJson(OutputRootSchema[list[RentalIncomeRecord]]):
    """Schema for ``aeat rental income list --json``."""


@app.command(name="record", help="Registrar (o actualizar) los ingresos de un contrato para un ejercicio.")
def record_cmd(
    contract_id: int = typer.Option(..., "--contract", help="Id del contrato."),
    period_year: int = typer.Option(..., "--period", help="Ejercicio (YYYY)."),
    gross_rent_received: str = typer.Option(..., "--amount", help="Ingreso íntegro del periodo."),
    dias_alquilados: int = typer.Option(365, "--dias-alquilados"),
) -> None:
    """Persist or update the per-contract per-period income."""
    with open_session() as session:
        contract_repo = RentalContractRepository(session)
        try:
            contract_repo.get(contract_id)
        except Exception as exc:
            raise ContractNotFoundError(
                f"contract id={contract_id} not found",
                context={"contract_id": contract_id},
            ) from exc
        income_repo = RentalIncomeRepository(session)
        record = RentalIncomeRecord(
            contract_id=contract_id,
            period_year=period_year,
            gross_rent_received=Decimal(gross_rent_received),
            dias_alquilados=dias_alquilados,
        )
        persisted = income_repo.upsert(record)
    if json_output_requested():
        emit_json_success("rental income record", IncomeRecordJson(record=persisted), sort_keys=True)
        return
    typer.echo(
        f"Recorded income for contract={persisted.contract_id} period={persisted.period_year} "
        f"amount={persisted.gross_rent_received}.",
    )


@app.command(name="list", help="Listar ingresos para un ejercicio.")
def list_cmd(
    period_year: int = typer.Option(..., "--period", help="Ejercicio (YYYY)."),
) -> None:
    with open_session() as session:
        income_repo = RentalIncomeRepository(session)
        records = income_repo.list_for_period(period_year)
    if json_output_requested():
        emit_json_success("rental income list", IncomeListJson(root=records), sort_keys=True)
        return
    if not records:
        typer.echo(f"No hay ingresos registrados para el ejercicio {period_year}.")
        return
    typer.echo("contract_id\tperiod\tgross_rent_received\tdias_alquilados")
    for record in records:
        typer.echo(
            "\t".join(
                [
                    str(record.contract_id),
                    str(record.period_year),
                    str(record.gross_rent_received),
                    str(record.dias_alquilados),
                ],
            ),
        )


__all__ = ["app"]
