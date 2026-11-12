"""The art. 52 individual sub-limit advisory over the real Modelo 100 revisions and calculation.

The earlier ejercicios' excess reduces first against the whole art. 52.1.b limit whatever its
origin (RIRPF art. 51), so a reduction that the excess alone takes above the 1.500 sub-limit is
no sign that the year's own personal contributions were over-reduced. Each exercise whose
revision calculates the reduction is taken from the support envelope; no year is written here.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import supported_exercises_with_projection
from ....domain.calculations.registry.tests.prevision_social_calculation_support import (
    calculate_m100_by_role,
    casilla_for_role,
)
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..art52_advisory import art52_reduccion_advisory_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FORMULA_ID = "renta-reduccion-prevision-social-total"
_ROLE_DINERARIO = "irpf_rendimiento_trabajo_importe_integro_dinerario"
_ROLE_REDUCCION = "irpf_reduccion_prevision_social_total"
_ROLE_TRABAJADOR = "irpf_red_prevision_social_aportaciones_trabajador"
_ROLE_EXCESO = "irpf_red_prevision_social_exceso_ejercicios_anteriores"


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one authority generation for the advisory under test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _calculating_snapshots() -> tuple[tuple[int, RegistrySnapshot], ...]:
    snapshots = (
        (year, published_snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION))
        for year in supported_exercises_with_projection("100")
    )
    return tuple(
        (year, snapshot)
        for year, snapshot in snapshots
        if any(formula.id == _FORMULA_ID for formula in snapshot.revision.formulas)
    )


def _calculated_values(snapshot: RegistrySnapshot, year: int, excess: Decimal) -> dict[CasillaId, Decimal]:
    """Net work 50.000 (30% = 15.000), own personal contribution 500, and the stated excess."""
    figures = {_ROLE_DINERARIO: Decimal("52000"), _ROLE_TRABAJADOR: Decimal("500"), _ROLE_EXCESO: excess}
    result = calculate_m100_by_role(snapshot, year, figures)
    return {validated_casilla_id(casilla): value for casilla, value in result.values.items()}


def _finding_raised(
    snapshot: RegistrySnapshot, year: int, values: dict[CasillaId, Decimal], operation: PinnedAuthorityOperation
) -> bool:
    finding = art52_reduccion_advisory_finding(
        snapshot.revision, values, operation=operation, modelo="100", effective_date=date(year, 12, 31)
    )
    return finding is not None


def test_an_excess_that_alone_takes_the_reduction_above_the_sublimit_is_silent(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Excess 4.000 and own 500 reduce in full: 0468 = 4.500, above 1.500, with no employer channel.

    The own part, 4.500 - 4.000 = 500, is within the 1.500 sub-limit, so nothing is advised.
    """
    calculated = _calculating_snapshots()
    assert calculated
    for year, snapshot in calculated:
        values = _calculated_values(snapshot, year, Decimal("4000"))

        assert values[validated_casilla_id(casilla_for_role(snapshot, _ROLE_REDUCCION))] == Decimal("4500.00"), year
        assert not _finding_raised(snapshot, year, values, authority_operation), year


def test_a_reduction_above_the_sublimit_without_an_excess_still_warns(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The same return with no excess, its 0468 stated at 3.000: 3.000 of own amounts exceed 1.500."""
    calculated = _calculating_snapshots()
    assert calculated
    for year, snapshot in calculated:
        values = _calculated_values(snapshot, year, Decimal("0"))
        values[validated_casilla_id(casilla_for_role(snapshot, _ROLE_REDUCCION))] = Decimal("3000")

        assert _finding_raised(snapshot, year, values, authority_operation), year


def test_an_excess_that_explains_only_part_of_the_reduction_still_warns(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Excess 4.000 with 0468 stated at 6.000 leaves 2.000 of own amounts, above the 1.500 sub-limit."""
    calculated = _calculating_snapshots()
    assert calculated
    for year, snapshot in calculated:
        values = _calculated_values(snapshot, year, Decimal("4000"))
        values[validated_casilla_id(casilla_for_role(snapshot, _ROLE_REDUCCION))] = Decimal("6000")

        assert _finding_raised(snapshot, year, values, authority_operation), year
