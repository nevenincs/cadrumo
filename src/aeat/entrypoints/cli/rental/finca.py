"""``aeat rental finca`` commands (#454)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import typer

from ....domain.rental import (
    FincaNotFoundError,
    RentalFinca,
    RentalFincaRepository,
    UseType,
)
from .._errors import json_output_requested
from .._schemas import OutputRootSchema, OutputSchema, emit_json_success, register_schema
from ._helpers import open_session

app = typer.Typer(
    name="finca",
    no_args_is_help=True,
    help="Gestión de fincas en el registro de alquileres (#454).",
)


@register_schema("rental finca list")
class FincaListJson(OutputRootSchema[list[RentalFinca]]):
    """Schema for ``aeat rental finca list --json``."""


@register_schema("rental finca show")
class FincaShowJson(OutputSchema):
    """Schema for ``aeat rental finca show --json``."""

    finca: RentalFinca


@register_schema("rental finca add")
class FincaAddJson(OutputSchema):
    """Schema for ``aeat rental finca add --json``."""

    finca: RentalFinca


@app.command(name="add", help="Registrar una nueva finca.")
def add_cmd(
    identifier: str = typer.Option(..., "--identifier", help="Identificador estable de la finca."),
    address: str = typer.Option(..., "--address", help="Dirección postal (cifrada en disco)."),
    valor_catastral_total: str = typer.Option(..., "--valor-catastral-total"),
    valor_catastral_construccion: str = typer.Option(..., "--valor-catastral-construccion"),
    coste_adquisicion: str = typer.Option(..., "--coste-adquisicion"),
    coste_adquisicion_construccion: str = typer.Option(..., "--coste-adquisicion-construccion"),
    acquisition_date: str = typer.Option(..., "--acquisition-date", help="ISO yyyy-mm-dd."),
    use_type: UseType = typer.Option(UseType.VIVIENDA_ARRENDADA, "--use-type"),
    is_stressed_area: bool = typer.Option(False, "--stressed-area / --no-stressed-area"),
    valor_catastral_revision_year: int | None = typer.Option(None, "--valor-catastral-revision-year"),
) -> None:
    """Persist a new finca and return the resulting record."""
    record = RentalFinca(
        identifier=identifier,
        address=address,
        valor_catastral_total=Decimal(valor_catastral_total),
        valor_catastral_construccion=Decimal(valor_catastral_construccion),
        valor_catastral_revision_year=valor_catastral_revision_year,
        coste_adquisicion=Decimal(coste_adquisicion),
        coste_adquisicion_construccion=Decimal(coste_adquisicion_construccion),
        acquisition_date=date.fromisoformat(acquisition_date),
        use_type=use_type,
        is_stressed_area=is_stressed_area,
    )
    with open_session() as session:
        repo = RentalFincaRepository(session)
        persisted = repo.upsert(record)
    if json_output_requested():
        emit_json_success("rental finca add", FincaAddJson(finca=persisted), sort_keys=True)
        return
    typer.echo(f"Registered finca {persisted.identifier} (id={persisted.id}).")


@app.command(name="list", help="Listar todas las fincas registradas.")
def list_cmd() -> None:
    """List all fincas in the register."""
    with open_session() as session:
        repo = RentalFincaRepository(session)
        records = repo.list_all()
    if json_output_requested():
        emit_json_success("rental finca list", FincaListJson(root=records), sort_keys=True)
        return
    if not records:
        typer.echo("No hay fincas registradas.")
        return
    typer.echo("identifier\tuse_type\tis_stressed_area\tvalor_catastral_total\taddress")
    for finca in records:
        typer.echo(
            "\t".join(
                [
                    finca.identifier,
                    finca.use_type.value,
                    "yes" if finca.is_stressed_area else "no",
                    f"{finca.valor_catastral_total}",
                    finca.address,
                ],
            ),
        )


@app.command(name="show", help="Mostrar una finca por su identificador.")
def show_cmd(identifier: str = typer.Argument(..., help="Identificador estable de la finca.")) -> None:
    with open_session() as session:
        repo = RentalFincaRepository(session)
        finca = repo.get_by_identifier(identifier)
        if finca is None:
            raise FincaNotFoundError(
                f"finca with identifier={identifier!r} not found",
                context={"identifier": identifier},
            )
    if json_output_requested():
        emit_json_success("rental finca show", FincaShowJson(finca=finca), sort_keys=True)
        return
    typer.echo(finca.model_dump_json(indent=2))


__all__ = ["app"]
