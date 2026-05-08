"""User-facing modelo registry introspection commands."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Annotated, Literal

import typer

from ...core.config import PROJECT_ROOT
from ...domain.calculations.registry import RegistryQueryService, ValidatedRegistryAuthority
from ...domain.calculations.registry._errors import RegistrySnapshotError
from ._common import _emit, _parse_iso_date

InputKind = Literal["manual", "bound", "computed", "informational"]

app = typer.Typer(
    name="modelo",
    help="Inspect modelo registry schemas, casillas, bindings, and formulas",
    no_args_is_help=True,
)


def _run_query[T](call: Callable[[], T]) -> T:
    """Run a registry-query call and translate user-input errors to clean CLI failures.

    ``RegistryQueryService`` raises :exc:`ValueError` from ``parse_modelo_period``
    on a malformed ``--period`` arg and :exc:`RegistrySnapshotError` from the
    authority on unknown modelo / unresolved revision. Both are user-input
    errors at the CLI boundary; surfacing them as ``typer.BadParameter``
    keeps the operator-facing experience clean rather than printing a
    traceback.
    """
    try:
        return call()
    except (ValueError, RegistrySnapshotError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("list")
def list_modelos(
    ctx: typer.Context,
    year: Annotated[int | None, typer.Option("--year", help="Filter modelos covering this filing year.")] = None,
) -> None:
    report = _run_query(lambda: _service().list_modelos(year=year))
    _emit(
        ctx,
        report,
        [
            "code\ttitle\tcadence\tdomain\trevisions",
            *[
                f"{row.code}\t{row.title}\t{row.cadence}\t{row.tax_domain}\t{row.revision_count}"
                for row in report.modelos
            ],
        ],
    )


@app.command("describe")
def describe_modelo(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Argument(help="Modelo code, for example 303 or 130.")],
    period: Annotated[str | None, typer.Option("--period", help="Filing period, for example 2026Q1.")] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help="Revision date selector in YYYY-MM-DD format.")] = None,
) -> None:
    report = _run_query(lambda: _service().describe_modelo(modelo, period=period, as_of=_as_of(as_of)))
    _emit(
        ctx,
        report,
        [
            f"Modelo\t{report.code}",
            f"Title\t{report.title}",
            f"Official name\t{report.official_name}",
            f"Tax domain\t{report.tax_domain}",
            f"Cadence\t{report.cadence}",
            f"Revision\t{report.revision}",
            f"Periods\t{', '.join(report.periods)}",
            f"Casillas\t{report.casilla_count}",
            f"Bindings\t{report.binding_count}",
            f"Formulas\t{report.formula_count}",
        ],
    )


@app.command("casillas")
def casillas(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Argument(help="Modelo code, for example 303 or 130.")],
    period: Annotated[str | None, typer.Option("--period", help="Filing period, for example 2026Q1.")] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help="Revision date selector in YYYY-MM-DD format.")] = None,
    input_kind: Annotated[
        InputKind | None,
        typer.Option("--input-kind", help="Filter by casilla input kind."),
    ] = None,
    required: Annotated[bool, typer.Option("--required", help="Show only required casillas.")] = False,
) -> None:
    report = _run_query(
        lambda: _service().casillas(
            modelo,
            period=period,
            as_of=_as_of(as_of),
            input_kind=input_kind,
            required=True if required else None,
        )
    )
    _emit(
        ctx,
        report,
        [
            "casilla_id\tnumber\tinput\trequired\tlabel",
            *[
                f"{row.casilla_id}\t{row.number}\t{row.input_kind}\t{str(row.required).lower()}\t{row.label}"
                for row in report.rows
            ],
        ],
    )


@app.command("bindings")
def bindings(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Argument(help="Modelo code, for example 303 or 130.")],
    period: Annotated[str | None, typer.Option("--period", help="Filing period, for example 2026Q1.")] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help="Revision date selector in YYYY-MM-DD format.")] = None,
) -> None:
    report = _run_query(lambda: _service().bindings(modelo, period=period, as_of=_as_of(as_of)))
    _emit(
        ctx,
        report,
        [
            "binding_id\tsource\ttyped_enum",
            *[f"{row.binding_id}\t{row.source}\t{row.typed_enum or '-'}" for row in report.rows],
        ],
    )


@app.command("formulas")
def formulas(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Argument(help="Modelo code, for example 303 or 130.")],
    period: Annotated[str | None, typer.Option("--period", help="Filing period, for example 2026Q1.")] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help="Revision date selector in YYYY-MM-DD format.")] = None,
) -> None:
    report = _run_query(lambda: _service().formulas(modelo, period=period, as_of=_as_of(as_of)))
    _emit(
        ctx,
        report,
        [
            "formula_id\ttarget\tinputs",
            *[
                f"{row.formula_id}\t{row.target}\t"
                f"{', '.join((*row.input_casillas, *row.input_bindings, *row.input_parameters))}"
                for row in report.rows
            ],
        ],
    )


def _service() -> RegistryQueryService:
    authority = ValidatedRegistryAuthority.load(PROJECT_ROOT / "registry" / "aeat", source_root=PROJECT_ROOT)
    return RegistryQueryService(authority)


def _as_of(raw: str | None) -> date | None:
    if raw is None:
        return None
    return _parse_iso_date(raw, label="--as-of")


__all__ = ["app"]
