"""Modelo 131's módulos parameter rows stay open past the newest authored edition.

Each year's Orden de módulos restates the unit amounts, the corrective-index
cuantías, the employment coefficients and the general reduction; while a value
is unchanged it is one open row that later editions inherit. The support
declaration's horizon is not a ceiling, so a year past it carries the newest
edition forward, and a row that closed at that edition's end would leave the
carried year without a value and the engine without a figure.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_formula import (
    BracketEntry,
    DatedValue,
    KeyedBracketEntry,
    ParameterDefinition,
)

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "131"
# The engine runs on the first quarter, which reads no earlier quarter's result.
_ENGINE_PERIOD = "1T"
_LAST_PERIOD = "4T"
_MODULOS_PARAMETER_PREFIX = "m131-modulos-"
# Peluquería (IAE 972.1): two employees, the owner, 50 m2 and 30 x 100 kWh.
_EPIGRAFE = "972.1"
_UNITS = {
    "modulos-1-unidades": Decimal("2"),
    "modulos-2-unidades": Decimal("1"),
    "modulos-3-unidades": Decimal("50"),
    "modulos-4-unidades": Decimal("30"),
    "modulos-5-unidades": Decimal("0"),
    "modulos-6-unidades": Decimal("0"),
    "modulos-7-unidades": Decimal("0"),
    "modulos-1-unidades-anterior": Decimal("0"),
    "modulos-minoracion-inversion": Decimal("0"),
}
_ENGINE_OUTPUTS = (
    "modulos-rendimiento-neto-previo",
    "modulos-rendimiento-neto-minorado",
    "modulos-rendimiento-neto-modulos",
    "modulos-rendimiento-neto-actividad",
)

type _Row = DatedValue | BracketEntry | KeyedBracketEntry


@cache
def _horizon() -> int:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    assert support.hard_ceiling is None or support.hard_ceiling > support.horizon, (
        "no year past the horizon is supported, so nothing is carried forward"
    )
    return support.horizon


@cache
def _snapshot(year: int, period: str) -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot(
        _MODELO,
        filing_year=year,
        period=period,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def _filing_rows(parameter: ParameterDefinition) -> Iterable[_Row]:
    yield from (row for row in parameter.values if row.date_axis is DateAxis.FILING_PERIOD)
    yield from parameter.brackets
    yield from parameter.keyed_brackets


def _rows_closing_by(parameters: Iterable[ParameterDefinition], last_day: date) -> dict[str, int]:
    """Count, per módulos parameter, the rows in force on ``last_day`` that end there."""
    closing: dict[str, int] = {}
    for parameter in parameters:
        if not parameter.id.startswith(_MODULOS_PARAMETER_PREFIX):
            continue
        in_force = [
            row
            for row in _filing_rows(parameter)
            if row.valid_from <= last_day and (row.valid_to is None or row.valid_to >= last_day)
        ]
        assert in_force, f"{parameter.id} has no row in force on {last_day}"
        ending = sum(1 for row in in_force if row.valid_to is not None)
        if ending:
            closing[parameter.id] = ending
    return closing


def _engine(snapshot: RegistrySnapshot) -> tuple[Decimal, ...]:
    assert snapshot.filing_period is not None
    result = calculate_registry_snapshot(
        snapshot,
        inputs=_UNITS,
        text_inputs={"modulos-epigrafe": _EPIGRAFE},
        date_context={"filing_period": snapshot.filing_period.end_date},
    )
    return tuple(result.values[casilla] for casilla in _ENGINE_OUTPUTS)


def test_the_newest_edition_leaves_its_modulos_rows_open() -> None:
    horizon = _horizon()
    parameters = _snapshot(horizon, _LAST_PERIOD).revision.parameters
    assert any(parameter.id.startswith(_MODULOS_PARAMETER_PREFIX) for parameter in parameters)
    assert _rows_closing_by(parameters, date(horizon, 12, 31)) == {}


def test_a_year_past_the_horizon_computes_the_horizon_figure() -> None:
    horizon = _horizon()
    at_horizon = _snapshot(horizon, _ENGINE_PERIOD)
    carried = _snapshot(horizon + 1, _ENGINE_PERIOD)
    assert carried.revision.id == at_horizon.revision.id
    figures = _engine(carried)
    assert figures == _engine(at_horizon)
    assert all(figure > 0 for figure in figures), figures


def test_a_row_closed_at_the_horizon_is_reported() -> None:
    """The open-row check reports a row that ends on the horizon's last day."""
    horizon = _horizon()
    last_day = date(horizon, 12, 31)
    reduction = next(
        parameter
        for parameter in _snapshot(horizon, _LAST_PERIOD).revision.parameters
        if parameter.id == f"{_MODULOS_PARAMETER_PREFIX}reduccion-general"
    )
    closed = reduction.model_copy(
        update={"values": tuple(row.model_copy(update={"valid_to": last_day}) for row in reduction.values)},
    )
    assert _rows_closing_by((reduction,), last_day) == {}
    assert _rows_closing_by((closed,), last_day) == {reduction.id: 1}
