"""Typer app exposing the ``aeat formulas`` subcommand surface (#173)."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from typing import Annotated

import typer

from ..errors import (
    AmbiguousPeriodError,
    AuditDiscrepancyError,
    CasillaNotDefinedError,
    FormulasError,
    MissingRulesetError,
)
from ..models import ModeloCode
from ._codes import Quarter
from ._engine import Engine
from ._period import FiscalPeriod
from ._registry import get_registry

app = typer.Typer(help="Per-modelo calculation formula engine (#173).", no_args_is_help=True)


def _format_json(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str)


def _parse_kv_pairs(pairs: tuple[str, ...]) -> dict[str, Decimal]:
    mapping: dict[str, Decimal] = {}
    for raw in pairs:
        if "=" not in raw:
            raise typer.BadParameter(f"expected KEY=VALUE, got {raw!r}")
        key, value = raw.split("=", 1)
        try:
            mapping[key.strip()] = Decimal(value.strip())
        except Exception as exc:
            raise typer.BadParameter(f"invalid decimal for {key!r}: {value!r}") from exc
    return mapping


def _parse_period(value: str) -> FiscalPeriod:
    text = value.strip().upper()
    if len(text) == 4 and text.isdigit():
        return FiscalPeriod(year=int(text))
    if len(text) == 6 and text[:4].isdigit() and text[4] == "Q" and text[5] in {"1", "2", "3", "4"}:
        return FiscalPeriod(year=int(text[:4]), quarter=Quarter(f"Q{text[5]}"))
    raise typer.BadParameter(f"invalid period {value!r}; expected e.g. 2024 or 2024Q2")


def _parse_modelo(value: str) -> ModeloCode:
    text = value.strip().upper()
    for candidate in ModeloCode:
        if candidate.name == text or candidate.value.upper() == text:
            return candidate
    raise typer.BadParameter(f"unknown modelo {value!r}")


@app.command("list")
def cmd_list() -> None:
    """List every ruleset id registered with the engine."""
    registry = get_registry()
    payload = [
        {
            "ruleset_id": ruleset.ruleset_id,
            "modelo": ruleset.modelo.value,
            "effective_from": ruleset.effective_from.isoformat(),
            "effective_to": ruleset.effective_to.isoformat() if ruleset.effective_to else None,
            "casilla_count": len(ruleset.casillas),
            "formula_count": len(ruleset.formulas),
        }
        for ruleset in registry.rulesets
    ]
    typer.echo(_format_json(payload))


@app.command("show")
def cmd_show(ruleset_id: Annotated[str, typer.Argument(help="Ruleset identifier (e.g. modelo_130.2024).")]) -> None:
    """Emit the full ruleset as JSON (casillas, formulas, parameters)."""
    registry = get_registry()
    for ruleset in registry.rulesets:
        if ruleset.ruleset_id == ruleset_id:
            typer.echo(ruleset.model_dump_json(indent=2))
            return
    raise typer.BadParameter(f"unknown ruleset {ruleset_id!r}")


@app.command("compute")
def cmd_compute(
    modelo: Annotated[str, typer.Option(..., help="Modelo code, e.g. MODELO_130.")],
    period: Annotated[str, typer.Option(..., help="Fiscal period, e.g. 2024Q2.")],
    input_pair: Annotated[
        list[str] | None,
        typer.Option(
            "--input",
            "-i",
            help="Casilla input as KEY=VALUE (repeatable).",
        ),
    ] = None,
) -> None:
    """Run the forward (derive) evaluator and emit the ledger as JSON."""
    registry = get_registry()
    modelo_code = _parse_modelo(modelo)
    fiscal_period = _parse_period(period)
    try:
        ruleset = registry.resolve(modelo=modelo_code, period=fiscal_period)
    except (MissingRulesetError, AmbiguousPeriodError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    inputs = _parse_kv_pairs(tuple(input_pair or ()))
    engine = Engine()
    try:
        ledger = engine.derive(ruleset=ruleset, inputs=inputs)
    except FormulasError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(ledger.model_dump_json(indent=2))


@app.command("audit")
def cmd_audit(
    modelo: Annotated[str, typer.Option(..., help="Modelo code, e.g. MODELO_130.")],
    period: Annotated[str, typer.Option(..., help="Fiscal period, e.g. 2024Q2.")],
    provided_pair: Annotated[
        list[str] | None,
        typer.Option(
            "--provided",
            "-p",
            help="Full casilla values as KEY=VALUE (repeatable).",
        ),
    ] = None,
    tolerance: Annotated[str, typer.Option(help="Discrepancy tolerance in EUR.")] = "0.01",
    strict: Annotated[bool, typer.Option(help="Exit non-zero when discrepancies exist.")] = False,
) -> None:
    """Run the reverse (audit) evaluator and emit the report as JSON."""
    registry = get_registry()
    modelo_code = _parse_modelo(modelo)
    fiscal_period = _parse_period(period)
    try:
        ruleset = registry.resolve(modelo=modelo_code, period=fiscal_period)
    except (MissingRulesetError, AmbiguousPeriodError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    provided = _parse_kv_pairs(tuple(provided_pair or ()))
    engine = Engine()
    try:
        report = engine.audit_against(
            ruleset=ruleset,
            provided=provided,
            tolerance=Decimal(tolerance),
        )
    except (FormulasError, CasillaNotDefinedError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(report.model_dump_json(indent=2))
    if strict:
        try:
            report.assert_clean()
        except AuditDiscrepancyError:
            raise typer.Exit(code=3) from None
    sys.stdout.flush()
