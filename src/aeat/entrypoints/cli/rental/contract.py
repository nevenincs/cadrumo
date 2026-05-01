"""``aeat rental contract`` commands (#454)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import typer

from ....domain.rental import (
    ContractNotFoundError,
    FincaNotFoundError,
    RentalContract,
    RentalContractRepository,
    RentalFincaRepository,
)
from .._errors import json_output_requested
from .._schemas import OutputRootSchema, OutputSchema, emit_json_success, register_schema
from ._helpers import open_session

app = typer.Typer(
    name="contract",
    no_args_is_help=True,
    help="Gestión de contratos de arrendamiento (#454).",
)


@register_schema("rental contract list")
class ContractListJson(OutputRootSchema[list[RentalContract]]):
    """Schema for ``aeat rental contract list --json``."""


@register_schema("rental contract show")
class ContractShowJson(OutputSchema):
    contract: RentalContract


@register_schema("rental contract add")
class ContractAddJson(OutputSchema):
    contract: RentalContract


@app.command(name="add", help="Registrar un contrato sobre una finca existente.")
def add_cmd(
    finca_identifier: str = typer.Option(..., "--finca", help="Identificador de la finca."),
    contract_celebration_date: str = typer.Option(..., "--celebration-date", help="ISO yyyy-mm-dd."),
    initial_rent: str = typer.Option(..., "--initial-rent"),
    tenant_count: int = typer.Option(1, "--tenant-count"),
    qualifying_co_tenant_count: int = typer.Option(0, "--qualifying-co-tenant-count"),
    tenant_min_age: int | None = typer.Option(None, "--tenant-min-age"),
    tenant_max_age: int | None = typer.Option(None, "--tenant-max-age"),
    tenant_is_public_admin: bool = typer.Option(False, "--public-admin / --no-public-admin"),
    is_first_rental: bool = typer.Option(False, "--first-rental / --no-first-rental"),
    rehabilitation_finished_date: str | None = typer.Option(None, "--rehab-finished-date"),
    prior_contract_last_rent: str | None = typer.Option(None, "--prior-rent"),
    lau_17_6_compliant: bool = typer.Option(True, "--lau-17-6-compliant / --no-lau-17-6-compliant"),
) -> None:
    """Register a contract on an existing finca."""
    with open_session() as session:
        finca_repo = RentalFincaRepository(session)
        finca = finca_repo.get_by_identifier(finca_identifier)
        if finca is None:
            raise FincaNotFoundError(
                f"finca with identifier={finca_identifier!r} not found",
                context={"finca_identifier": finca_identifier},
            )
        assert finca.id is not None
        record = RentalContract(
            finca_id=finca.id,
            contract_celebration_date=date.fromisoformat(contract_celebration_date),
            tenant_count=tenant_count,
            qualifying_co_tenant_count=qualifying_co_tenant_count,
            tenant_min_age=tenant_min_age,
            tenant_max_age=tenant_max_age,
            tenant_is_public_admin=tenant_is_public_admin,
            initial_rent=Decimal(initial_rent),
            is_first_rental=is_first_rental,
            rehabilitation_finished_date=date.fromisoformat(rehabilitation_finished_date)
            if rehabilitation_finished_date is not None
            else None,
            prior_contract_last_rent=Decimal(prior_contract_last_rent)
            if prior_contract_last_rent is not None
            else None,
            lau_17_6_compliant=lau_17_6_compliant,
        )
        contract_repo = RentalContractRepository(session)
        persisted = contract_repo.upsert(record)
    if json_output_requested():
        emit_json_success("rental contract add", ContractAddJson(contract=persisted), sort_keys=True)
        return
    typer.echo(f"Registered contract id={persisted.id} on finca {finca.identifier}.")


@app.command(name="list", help="Listar contratos (todos o por finca).")
def list_cmd(
    finca_identifier: str | None = typer.Option(None, "--finca", help="Filtrar por finca."),
) -> None:
    """List contracts, optionally filtering by finca identifier."""
    with open_session() as session:
        contract_repo = RentalContractRepository(session)
        if finca_identifier is not None:
            finca_repo = RentalFincaRepository(session)
            finca = finca_repo.get_by_identifier(finca_identifier)
            if finca is None:
                raise FincaNotFoundError(
                    f"finca with identifier={finca_identifier!r} not found",
                    context={"finca_identifier": finca_identifier},
                )
            assert finca.id is not None
            records = contract_repo.list_for_finca(finca.id)
        else:
            records = contract_repo.list_all()
    if json_output_requested():
        emit_json_success("rental contract list", ContractListJson(root=records), sort_keys=True)
        return
    if not records:
        typer.echo("No hay contratos registrados.")
        return
    typer.echo("id\tfinca_id\tcelebration\ttermination\ttenant_count\tinitial_rent")
    for contract in records:
        typer.echo(
            "\t".join(
                [
                    str(contract.id),
                    str(contract.finca_id),
                    contract.contract_celebration_date.isoformat(),
                    contract.contract_termination_date.isoformat()
                    if contract.contract_termination_date is not None
                    else "-",
                    str(contract.tenant_count),
                    str(contract.initial_rent),
                ],
            ),
        )


@app.command(name="show", help="Mostrar un contrato por id.")
def show_cmd(contract_id: int = typer.Argument(..., help="Id de contrato.")) -> None:
    with open_session() as session:
        repo = RentalContractRepository(session)
        try:
            contract = repo.get(contract_id)
        except Exception as exc:
            raise ContractNotFoundError(
                f"contract id={contract_id} not found",
                context={"contract_id": contract_id},
            ) from exc
    if json_output_requested():
        emit_json_success("rental contract show", ContractShowJson(contract=contract), sort_keys=True)
        return
    typer.echo(contract.model_dump_json(indent=2))


__all__ = ["app"]
