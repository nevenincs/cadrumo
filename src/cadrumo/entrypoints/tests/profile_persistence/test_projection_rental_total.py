"""The Modelo 100 projection weighs the let properties' net rent in the art. 20 other-income limit.

The total comes from the same ``renta_inmueble`` resolver as the annual calculation. A property
with net rent counts, a filer with no let property states a proven 0.00, and a property whose
net yield cannot be worked out leaves the total unresolved instead of reading as zero.

The expected net yield is worked by hand from the property's stated figures: twelve rents of
900.00 less the 3 per 100 amortisation of the greater of the construction share of the cost
((99.000 + 1.000) x 80 %) and the cadastral construction value (64.000). The property is
acquired on the first day of the ejercicio, so no earlier pending amounts are in question.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.aggregation.tests.renta_inmueble_support import inmueble, lease, profile_facts, rent
from cadrumo.application.modelo.projection import ModeloProjectServiceResult
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.contribuyente.inmueble_record import AdquisicionTitulo, ValorCatastral
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.domain.transactions.models import Transaction
from cadrumo.domain.user_profile.values import UserProfileFact

from .projection_m130_seeding_support import PROJECTION_YEAR, run_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CATEGORIES = "actividad_economica,capital_inmobiliario"
_TOTAL_BINDING = "renta-inmueble-total-rendimiento-neto-0149"
_OTHER_RENTAS = "rentas-distintas-del-trabajo"
_NET_RENT = Decimal("10800.00") - Decimal("2400.00")


def _let_facts(*, complete: bool) -> tuple[UserProfileFact, ...]:
    held = inmueble(
        ejercicio=PROJECTION_YEAR,
        adquisicion_titulo=AdquisicionTitulo.ONEROSA,
        fecha_adquisicion=date(PROJECTION_YEAR, 1, 1),
        importe_adquisicion=Decimal(99000) if complete else None,
        gastos_tributos_adquisicion=Decimal(1000) if complete else None,
        valores_catastrales=(
            (ValorCatastral(year=PROJECTION_YEAR, total=Decimal(80000), construccion=Decimal(64000)),)
            if complete
            else ()
        ),
    )
    stated = profile_facts((held,), (lease(start=date(PROJECTION_YEAR, 1, 1)),))
    return tuple(UserProfileFact(path=path, value=value) for path, value in stated.items())


def _rents() -> tuple[Transaction, ...]:
    return tuple(
        rent(
            f"rent-{month}",
            amount=Decimal(900),
            booked=date(PROJECTION_YEAR, month, 1),
            business_classification=BusinessClassification.PERSONAL,
        )
        for month in range(1, 13)
    )


def _other_rentas(result: ModeloProjectServiceResult) -> Decimal | None:
    return next((row.value for row in result.casilla_observations if row.casilla_id == _OTHER_RENTAS), None)


def test_a_let_property_with_net_rent_counts_in_the_art_20_other_rentas(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    without = run_projection(tmp_path / "none", operation, income_categories=_CATEGORIES)
    let = run_projection(
        tmp_path / "let",
        operation,
        income_categories=_CATEGORIES,
        profile_facts=_let_facts(complete=True),
        ledger_rows=_rents(),
    )

    base = _other_rentas(without)
    assert base is not None
    assert _other_rentas(let) == base + _NET_RENT
    assert _TOTAL_BINDING not in {row.binding_id for row in let.unresolved_bindings}
    # The estimate stays an estimate.
    assert let.is_extrapolated


def test_a_let_property_whose_net_yield_is_unknown_leaves_the_other_rentas_unresolved_not_zero(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    result = run_projection(
        tmp_path,
        operation,
        income_categories=_CATEGORIES,
        profile_facts=_let_facts(complete=False),
        ledger_rows=_rents(),
    )

    assert _TOTAL_BINDING in {row.binding_id for row in result.unresolved_bindings}
    assert _other_rentas(result) is None


def test_no_let_property_is_a_proven_zero_rental_total(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    result = run_projection(tmp_path, operation, income_categories=_CATEGORIES)

    assert _TOTAL_BINDING not in {row.binding_id for row in result.unresolved_bindings}
    # Only the annualised Modelo 130 activity income (6.000.00 to the first quarter, four quarters) counts.
    assert _other_rentas(result) == Decimal("24000.00")
