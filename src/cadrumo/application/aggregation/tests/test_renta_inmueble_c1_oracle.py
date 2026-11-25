"""Anexo C.1 of one let property against figures worked by hand from LIRPF art. 23.1.a.1.º and RIRPF art. 13.a.

The rule: the interest and repair excess of earlier ejercicios is applied
before the year's own amounts, within the property's gross income; the oldest
origin year goes first; what an origin year inside the window cannot apply
carries on, and what the oldest origin year of the window cannot apply
expires, so it has no box. 0103 and 0104 are the sums of the openings and of
the applied amounts. The holder and the referencia catastral fill 1211 and
1212 only when the annex carries an amount.

Every expected figure below is computed by hand from that rule, for a rent of
10.800 and repairs of 1.000, and the carry window is the four years the law
states (Manual práctico de Renta: "El exceso se podrá deducir en los cuatro
años siguientes"), which the registry parameter must declare.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.renta_inmueble_bindings import RentaInmuebleOriginPart
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision_operator_layer import RowCarryAttestation
from ..renta_inmueble_findings import RentaInmuebleCause
from ..renta_inmueble_source import RentaInmuebleRowField
from ..source_mesh import CalculationSourceResolution
from .ledger_source_mesh_support import m100_revision
from .renta_inmueble_carry_support import PENDING_CAUSES, column, findings, origin_column, resolve_carry, stated, window
from .renta_inmueble_support import REFERENCIA_CATASTRAL

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEARS = filing_year_envelope().years
_OPENING = RentaInmuebleOriginPart.OPENING
_APPLIED = RentaInmuebleOriginPart.APPLIED
_CARRIED = RentaInmuebleOriginPart.CARRIED
_LAW_WINDOW = 4


def _resolve(year: int, *statements: RowCarryAttestation) -> CalculationSourceResolution:
    """Resolve the property first let, and let under its lease, since the first year of the carry window."""
    start = date(year - _LAW_WINDOW, 1, 1)
    return resolve_carry(year, *statements, arrendado_desde=start, lease_start=start)


def _boxes(year: int, resolution: CalculationSourceResolution) -> dict[tuple[str, int], object]:
    """Return every anexo C.1 origin box the row fills, keyed by part and origin back."""
    revision = m100_revision(year)
    resolution_values = resolution.row_binding_values
    filled: dict[tuple[str, int], object] = {}
    for part in RentaInmuebleOriginPart:
        for back in range(1, window(revision) + 1):
            if part is _CARRIED and back == window(revision):
                continue
            value = resolution_values.get((origin_column(revision, part, back), 1))
            if value is not None:
                filled[(part.value, back)] = value
    return filled


@pytest.mark.parametrize("year", _YEARS)
def test_the_registry_window_is_the_four_years_the_law_states(year: int) -> None:
    revision = m100_revision(year)

    assert window(revision) == _LAW_WINDOW
    with pytest.raises(KeyError):
        origin_column(revision, _CARRIED, _LAW_WINDOW)


@pytest.mark.parametrize("year", _YEARS)
def test_origins_apply_oldest_first_within_the_income_and_the_newest_carries_the_rest(year: int) -> None:
    revision = m100_revision(year)
    resolution = _resolve(
        year,
        stated(year, 4, "3000"),
        stated(year, 3, "2100"),
        stated(year, 2, "4000"),
        stated(year, 1, "2500"),
    )
    values = dict(resolution.row_binding_values)

    for cause in PENDING_CAUSES:
        assert findings(resolution, cause) == [], (year, cause)
    # Room 10.800: 3.000, 2.100 and 4.000 apply whole (1.700 left), the newest origin applies 1.700 of
    # its 2.500 and carries 800; the year's own 1.000 finds no room and is pending as a whole.
    assert _boxes(year, resolution) == {
        ("opening", 4): Decimal(3000),
        ("applied", 4): Decimal(3000),
        ("opening", 3): Decimal(2100),
        ("applied", 3): Decimal(2100),
        ("opening", 2): Decimal(4000),
        ("applied", 2): Decimal(4000),
        ("opening", 1): Decimal(2500),
        ("applied", 1): Decimal(1700),
        ("carried", 1): Decimal(800),
    }
    assert values[(column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES), 1)] == Decimal(11600)
    assert values[(column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_APLICADOS), 1)] == Decimal(10800)
    assert (column(revision, RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS), 1) not in values
    assert values[(column(revision, RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES), 1)] == Decimal(1000)
    assert values[(column(revision, RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES_FUTUROS), 1)] == Decimal(1000)
    assert values[(column(revision, RentaInmuebleRowField.ANEXO_C1_TITULAR), 1)] == "declarante"
    assert values[(column(revision, RentaInmuebleRowField.ANEXO_C1_REFERENCIA_CATASTRAL), 1)] == REFERENCIA_CATASTRAL


@pytest.mark.parametrize("year", _YEARS)
def test_what_the_oldest_origin_cannot_apply_expires_and_the_others_carry_whole(year: int) -> None:
    revision = m100_revision(year)
    resolution = _resolve(
        year,
        stated(year, 4, "12000"),
        stated(year, 3, "500"),
        stated(year, 2, None),
        stated(year, 1, "300"),
    )
    values = dict(resolution.row_binding_values)

    # The oldest origin takes the whole 10.800 and its last 1.200 expire with this return; the
    # other origins apply nothing and carry their whole amount; the year's own 1.000 is pending.
    assert _boxes(year, resolution) == {
        ("opening", 4): Decimal(12000),
        ("applied", 4): Decimal(10800),
        ("opening", 3): Decimal(500),
        ("carried", 3): Decimal(500),
        ("opening", 1): Decimal(300),
        ("carried", 1): Decimal(300),
    }
    assert values[(column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES), 1)] == Decimal(12800)
    assert values[(column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_APLICADOS), 1)] == Decimal(10800)
    assert values[(column(revision, RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES), 1)] == Decimal(1000)


@pytest.mark.parametrize("year", _YEARS)
def test_a_property_carrying_nothing_fills_no_annex_box(year: int) -> None:
    revision = m100_revision(year)
    resolution = _resolve(year, *(stated(year, back, None) for back in range(1, _LAW_WINDOW + 1)))
    values = dict(resolution.row_binding_values)

    assert _boxes(year, resolution) == {}
    for field in (RentaInmuebleRowField.ANEXO_C1_TITULAR, RentaInmuebleRowField.ANEXO_C1_REFERENCIA_CATASTRAL):
        assert (column(revision, field), 1) not in values
    assert values[(column(revision, RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS), 1)] == Decimal(1000)
    assert findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == []
