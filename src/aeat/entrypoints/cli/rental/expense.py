"""``aeat rental expense`` Typer commands.

Record and list deductible rental expenses by finca + ejercicio,
classified by :class:`aeat.domain.rental.ExpenseCategory` per LIRPF
art. 23.1. Persistence flows through
:class:`aeat.domain.rental.RentalExpenseRepository`.
"""

from __future__ import annotations

from decimal import Decimal

import typer

from ....domain.rental import (
    ExpenseCategory,
    FincaNotFoundError,
    RentalExpense,
    RentalExpenseRepository,
    RentalFincaRepository,
)
from .._errors import json_output_requested
from .._schemas import OutputRootSchema, OutputSchema, emit_json_success, register_schema
from ._helpers import open_session

app = typer.Typer(
    name="expense",
    no_args_is_help=True,
    help="Registro de gastos deducibles por finca/ejercicio.",
)


@register_schema("rental expense add")
class ExpenseAddJson(OutputSchema):
    """Schema for ``aeat rental expense add --json``.

    Attributes:
        expense: The newly persisted :class:`RentalExpense` record.
    """

    expense: RentalExpense


@register_schema("rental expense list")
class ExpenseListJson(OutputRootSchema[list[RentalExpense]]):
    """Schema for ``aeat rental expense list --json``."""


@app.command(name="add", help="Registrar un gasto deducible (LIRPF art. 23.1).")
def add_cmd(
    finca_identifier: str = typer.Option(..., "--finca"),
    period_year: int = typer.Option(..., "--period"),
    category: ExpenseCategory = typer.Option(..., "--category"),
    amount: str = typer.Option(..., "--amount"),
) -> None:
    """Persist one deductible expense for a finca and ejercicio.

    Raises:
        FincaNotFoundError: When ``finca_identifier`` is unknown.
    """
    with open_session() as session:
        finca_repo = RentalFincaRepository(session)
        finca = finca_repo.get_by_identifier(finca_identifier)
        if finca is None:
            raise FincaNotFoundError(
                f"finca with identifier={finca_identifier!r} not found",
                context={"finca_identifier": finca_identifier},
            )
        assert finca.id is not None
        expense_repo = RentalExpenseRepository(session)
        record = RentalExpense(
            finca_id=finca.id,
            period_year=period_year,
            category=category,
            amount=Decimal(amount),
        )
        persisted = expense_repo.add(record)
    if json_output_requested():
        emit_json_success("rental expense add", ExpenseAddJson(expense=persisted), sort_keys=True)
        return
    typer.echo(
        f"Recorded expense id={persisted.id} on finca {finca.identifier} "
        f"category={persisted.category.value} amount={persisted.amount}.",
    )


@app.command(name="list", help="Listar gastos de una finca para un ejercicio.")
def list_cmd(
    finca_identifier: str = typer.Option(..., "--finca"),
    period_year: int = typer.Option(..., "--period"),
) -> None:
    """List every expense recorded for ``finca_identifier`` in ``period_year``.

    Raises:
        FincaNotFoundError: When ``finca_identifier`` is unknown.
    """
    with open_session() as session:
        finca_repo = RentalFincaRepository(session)
        finca = finca_repo.get_by_identifier(finca_identifier)
        if finca is None:
            raise FincaNotFoundError(
                f"finca with identifier={finca_identifier!r} not found",
                context={"finca_identifier": finca_identifier},
            )
        assert finca.id is not None
        expense_repo = RentalExpenseRepository(session)
        records = expense_repo.list_for_finca_period(finca.id, period_year)
    if json_output_requested():
        emit_json_success("rental expense list", ExpenseListJson(root=records), sort_keys=True)
        return
    if not records:
        typer.echo(f"No hay gastos para finca {finca_identifier} en el ejercicio {period_year}.")
        return
    typer.echo("id\tcategory\tamount")
    for record in records:
        typer.echo(f"{record.id}\t{record.category.value}\t{record.amount}")


__all__ = ["app"]
