"""The registered Modelo 100 projection reads the art. 85 imputed property income total, casilla 0089, into 0155.

Casilla 0155 sums the income imputed on every Inmueble row. The projection takes that total from the same
``renta_inmueble`` resolver the annual calculation uses: a filer whose stated properties carry no imputed income
projects without refusal, with the total a proven 0.00 over the properties the profile states, and a flat at its
owner's disposal counts its imputed income in the estimate.

The flat has the 2025 Renta manual's cadastral value of 46.200, revised in a collective valuation in force, and
is at its owner's disposal the whole year, so it imputes the manual's 1,1 % of that value: 508,20.

Real behaviour throughout: an isolated encrypted profile, the published authority, the executor the production
operation registry composes for ``modelo.project``, every year of the registry's support envelope whose Modelo 100
revision the registry's projection declaration names.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....application.aggregation.tests.renta_inmueble_support import inmueble, profile_facts
from ....application.modelo.projection_declaration import modelo_projection_available
from ....application.modelo.projection_operation import ModeloProjectOperationProjection
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.contribuyente.inmueble_record import UsoInmueble, UsoInmuebleTipo, ValorCatastral
from ....domain.user_profile.values import UserProfileFact
from .projection_m130_seeding_support import run_registered_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CATEGORIES = "actividad_economica,capital_inmobiliario"
_IMPUTED_TOTAL = "renta-inmueble-total-renta-imputada-0089"
_SUM_BOX = "0155"
_VALUE = Decimal("46200")
_REDUCED = Decimal("0.011")


def _projectable_years() -> tuple[int, ...]:
    """The years of the support envelope whose Modelo 100 revision the registry's projection declaration names."""
    support = published_supported_filing_years()
    assert support is not None
    operation = published_authority_operation()
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            snapshot = operation.snapshot(
                "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
            )
        except FilingYearOutsideSupportEnvelopeError:
            continue
        if modelo_projection_available(
            modelo="100",
            period=Period.from_year_and_code(year, "0A"),
            filing_year=year,
            registry_revision_id=str(snapshot.revision.id),
            operation=operation,
        ):
            admitted.append(year)
    assert admitted, "the registry declares no projectable Modelo 100 year"
    return tuple(admitted)


def _flat_at_disposal(year: int) -> tuple[UserProfileFact, ...]:
    """A flat at its owner's disposal for the whole of ``year`` and never let."""
    record = inmueble(
        ejercicio=year,
        importe_adquisicion=Decimal(150000),
        gastos_tributos_adquisicion=Decimal(10000),
        valores_catastrales=(ValorCatastral(year=year, total=_VALUE, construccion=Decimal(27720), vigor=year),),
        usos=(UsoInmueble(tipo=UsoInmuebleTipo.DISPOSICION_PROPIETARIO, desde=date(year - 2, 1, 1), hasta=None),),
    )
    stated = profile_facts((record,), ())
    return tuple(UserProfileFact(path=path, value=value) for path, value in stated.items())


def _box(result: ModeloProjectOperationProjection, casilla_id: str) -> Decimal | None:
    value = next((row.value for row in result.casilla_observations if row.casilla_id == casilla_id), None)
    return None if value is None else Decimal(str(value))


def _unresolved(result: ModeloProjectOperationProjection) -> set[str]:
    return {row.binding_id for row in result.unresolved_bindings}


@pytest.mark.parametrize("year", _projectable_years())
def test_a_filer_with_no_property_is_projected_with_no_imputed_income(tmp_path: Path, year: int) -> None:
    result = run_registered_projection(tmp_path, year=year)

    assert result.year == year
    assert _IMPUTED_TOTAL not in _unresolved(result)
    assert _box(result, _SUM_BOX) == Decimal("0.00")


@pytest.mark.parametrize("year", _projectable_years())
def test_a_flat_at_its_owners_disposal_all_year_counts_its_imputed_income_in_the_projection(
    tmp_path: Path, year: int
) -> None:
    result = run_registered_projection(
        tmp_path, year=year, income_categories=_CATEGORIES, profile_facts=_flat_at_disposal(year)
    )
    # A whole year at the owner's disposal imputes the whole rate on the cadastral value.
    expected = (_VALUE * _REDUCED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    assert _IMPUTED_TOTAL not in _unresolved(result)
    assert _box(result, _SUM_BOX) == expected
