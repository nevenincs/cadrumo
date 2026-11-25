"""Which origin years of anexo C.1 a let property must state, from what its records store.

Only an ejercicio in which the property was let can have left an interest and
repair excess, so the property record's first letting decides which origin
years of the carry window need a statement: those not before it. A property
first let inside the ejercicio needs none. A lease that started before the
ejercicio is itself a stored sign of earlier letting, but it never stands in
for an unstated start: every origin year of the window is then asked for. An
unstated start blocks on its own, with the property door, even for a property
let only inside the ejercicio.

A held earlier return is not read for these amounts; the finding says so and
still asks for the statement. A carry stated as one total before anexo C.1
was followed by origin year answers every origin year when it is nothing, and
asks for the split when it is an amount.

Real behaviour: the published Modelo 100 revision of every year of the support
envelope, the real profile record and the real resolver; the window rule is
also exercised directly on the property record for the never-let state, which
a profile with a lease cannot hold.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry.renta_inmueble_bindings import RentaInmuebleOriginPart
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO, RowCarryAttestation
from ..renta_inmueble_carry import carry_window
from ..renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleDoor
from ..renta_inmueble_period import Ejercicio
from ..renta_inmueble_source import RentaInmuebleRowField
from ..source_mesh import CalculationSourceResolution
from .ledger_source_mesh_support import m100_revision
from .renta_inmueble_carry_support import (
    PENDING_CAUSES,
    ROW,
    column,
    findings,
    origin_column,
    resolve_carry,
    stated,
    window,
)
from .renta_inmueble_support import inmueble, lease

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEARS = filing_year_envelope().years


def _asked(year: int, resolution: CalculationSourceResolution, cause: RentaInmuebleCause) -> set[int]:
    """Return the origin backs whose opening column a finding of ``cause`` asks for."""
    revision = m100_revision(year)
    backs = {
        origin_column(revision, RentaInmuebleOriginPart.OPENING, back): back for back in range(1, window(revision) + 1)
    }
    asked: set[int] = set()
    for finding in findings(resolution, cause):
        assert finding.fact is not None
        asked.add(backs[dict(finding.fact.values)["binding"]])
    return asked


def _total(year: int, amount: str | None) -> RowCarryAttestation:
    """The carry stated as one total on 0103, as before anexo C.1 was followed by origin year."""
    whole = column(m100_revision(year), RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES)
    if amount is None:
        return RowCarryAttestation(binding_id=whole, source_row_identity=ROW, amount=ATTESTED_ZERO, absent=True)
    return RowCarryAttestation(binding_id=whole, source_row_identity=ROW, amount=amount)


@pytest.mark.parametrize("year", _YEARS)
def test_a_start_before_the_ejercicio_asks_only_for_the_origin_years_not_before_it(year: int) -> None:
    resolution = resolve_carry(year, arrendado_desde=date(year - 2, 7, 1), lease_start=date(year - 2, 7, 1))

    assert _asked(year, resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == {1, 2}
    assert findings(resolution, RentaInmuebleCause.LETTING_START_UNSTATED) == []


@pytest.mark.parametrize("year", _YEARS)
def test_a_start_long_before_the_ejercicio_asks_for_the_whole_window(year: int) -> None:
    revision = m100_revision(year)
    long_ago = date(year - window(revision) - 3, 1, 1)
    resolution = resolve_carry(year, arrendado_desde=long_ago, lease_start=long_ago)

    assert _asked(year, resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == set(range(1, window(revision) + 1))


@pytest.mark.parametrize("year", _YEARS)
def test_a_property_first_let_in_the_ejercicio_raises_nothing(year: int) -> None:
    resolution = resolve_carry(year, arrendado_desde=date(year, 1, 1), lease_start=date(year, 1, 1))

    for cause in PENDING_CAUSES:
        assert findings(resolution, cause) == [], (year, cause)
    assert (column(m100_revision(year), RentaInmuebleRowField.RENDIMIENTO_NETO), 1) in resolution.row_binding_values


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_start_blocks_on_the_start_even_when_let_only_in_the_ejercicio(year: int) -> None:
    resolution = resolve_carry(year, start_unstated=True, lease_start=date(year, 1, 1))

    (finding,) = findings(resolution, RentaInmuebleCause.LETTING_START_UNSTATED)
    assert finding.reason == "source_domain_not_ready"
    assert finding.remedy is not None and RentaInmuebleDoor.INMUEBLE_EDIT.value in finding.remedy
    assert findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == []


@pytest.mark.parametrize("year", _YEARS)
def test_an_earlier_lease_with_an_unstated_start_asks_for_the_whole_window_and_the_start(year: int) -> None:
    revision = m100_revision(year)
    resolution = resolve_carry(year, start_unstated=True, lease_start=date(year - 1, 6, 1))

    assert len(findings(resolution, RentaInmuebleCause.LETTING_START_UNSTATED)) == 1
    assert _asked(year, resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == set(range(1, window(revision) + 1))


@pytest.mark.parametrize("year", _YEARS)
def test_a_held_earlier_return_is_said_to_be_unread_and_the_statement_is_still_asked(year: int) -> None:
    resolution = resolve_carry(year, arrendado_desde=date(year - 1, 1, 1), lease_start=date(year - 1, 1, 1), held=True)

    assert findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == []
    assert _asked(year, resolution, RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED) == {1}

    settled = resolve_carry(
        year,
        stated(year, 1, None),
        arrendado_desde=date(year - 1, 1, 1),
        lease_start=date(year - 1, 1, 1),
        held=True,
    )
    for cause in PENDING_CAUSES:
        assert findings(settled, cause) == [], (year, cause)


@pytest.mark.parametrize("year", _YEARS)
def test_a_total_of_nothing_stated_before_the_split_answers_every_origin_year(year: int) -> None:
    resolution = resolve_carry(year, _total(year, None))

    for cause in PENDING_CAUSES:
        assert findings(resolution, cause) == [], (year, cause)


@pytest.mark.parametrize("year", _YEARS)
def test_a_total_amount_stated_before_the_split_asks_for_each_origin_year(year: int) -> None:
    resolution = resolve_carry(year, _total(year, "500"), stated(year, 2, None))

    assert _asked(year, resolution, RentaInmuebleCause.PENDING_EXPENSES_TOTAL_UNSPLIT) == {1, 3}
    assert findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == []
    assert (column(m100_revision(year), RentaInmuebleRowField.RENDIMIENTO_NETO), 1) not in (
        resolution.row_binding_values
    )


def test_the_window_rule_reads_only_the_stored_facts() -> None:
    year = filing_year_envelope().horizon
    ejercicio = Ejercicio(first=date(year, 1, 1), last=date(year, 12, 31))
    earlier = (lease(start=date(year - 2, 3, 1)),)
    inside = (lease(start=date(year, 3, 1)),)
    width = 4

    never = carry_window(inmueble(ejercicio=year, sin_arrendar=True), (), ejercicio, width)
    assert (never.backs, never.start_unstated) == ((), False)
    unstated = carry_window(inmueble(ejercicio=year), inside, ejercicio, width)
    assert (unstated.backs, unstated.start_unstated) == ((), True)
    unstated_earlier = carry_window(inmueble(ejercicio=year), earlier, ejercicio, width)
    assert (unstated_earlier.backs, unstated_earlier.start_unstated) == ((1, 2, 3, 4), True)
    late_day = carry_window(inmueble(ejercicio=year, arrendado_desde=date(year - 1, 12, 31)), (), ejercicio, width)
    assert late_day.backs == (1,)
    first_day = carry_window(inmueble(ejercicio=year, arrendado_desde=date(year, 1, 1)), inside, ejercicio, width)
    assert first_day.backs == ()


@pytest.mark.parametrize("year", _YEARS)
def test_the_carry_left_by_an_origin_year_never_reaches_a_net_yield_while_unknown(year: int) -> None:
    resolution = resolve_carry(year, stated(year, 1, "100"), stated(year, 2, None))

    assert _asked(year, resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == {3}
    assert (column(m100_revision(year), RentaInmuebleRowField.RENDIMIENTO_NETO), 1) not in (
        resolution.row_binding_values
    )
