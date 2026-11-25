"""Modelo 130 box 03 is computed after the LIRPF art. 32.1 reduction.

The instructions for box 03: such yields "se computarán a efectos del pago fraccionado
previa aplicación de la reducción". Art. 32.1 reduces them by 30 per cent on at most
300.000 euros a year. Only the operator's typed figure says a yield qualifies, because
the article also excludes activities that regularly obtain such yields.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import validated_casilla_id, validated_casilla_id_map
from ..authority import PinnedAuthorityOperation
from ..formula_runtime import calculate_registry_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_DECLARED = 2025
_REDUCIBLE = "rendimiento-neto-reducible-art-32-1"
_EXPENSES = "gastos-deducibles-previos"


def _boxes(operation: PinnedAuthorityOperation, typed: Mapping[str, str]) -> dict[str, Decimal]:
    result = calculate_registry_snapshot(
        operation.snapshot("130", filing_year=_DECLARED, period="1T"),
        inputs=validated_casilla_id_map(
            {key: Decimal(value) for key, value in typed.items()},
            surface="art. 32.1 test inputs",
        ),
        date_context={"filing_period": date(_DECLARED, 4, 20)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("100000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
        },
        # The normal modality keeps box 02 equal to the typed expenses.
        enum_binding_values={"modelo-130-estimacion-directa-modalidad": "directa_normal"},
    )
    return {str(entry.target_casilla_id): entry.value for entry in result.entries}


def test_a_multi_year_yield_is_reduced_before_the_twenty_per_cent(*, operation: PinnedAuthorityOperation) -> None:
    """50000 - 40000 x 0,30 = 38000; 38000 x 0,20 = 7600."""
    boxes = _boxes(operation, {"01": "50000", _EXPENSES: "0", _REDUCIBLE: "40000"})

    assert boxes["03"] == Decimal("38000.00"), boxes
    assert boxes["04"] == Decimal("7600.00"), boxes


def test_the_reduction_stops_at_the_annual_ceiling(*, operation: PinnedAuthorityOperation) -> None:
    """500000 - 300000 x 0,30 = 410000, not 500000 - 400000 x 0,30 = 380000."""
    boxes = _boxes(operation, {"01": "500000", _EXPENSES: "0", _REDUCIBLE: "400000"})

    assert boxes["03"] == Decimal("410000.00"), boxes


def test_no_typed_figure_reduces_nothing(*, operation: PinnedAuthorityOperation) -> None:
    boxes = _boxes(operation, {"01": "50000", _EXPENSES: "0"})

    assert boxes["03"] == Decimal("50000.00"), boxes
    assert boxes["04"] == Decimal("10000.00"), boxes


def test_the_figure_is_a_working_input_and_not_a_box_on_the_form(*, operation: PinnedAuthorityOperation) -> None:
    snapshot = operation.snapshot("130", filing_year=_DECLARED, period="1T")
    casilla = next(item for item in snapshot.revision.casillas if item.id == validated_casilla_id(_REDUCIBLE))

    assert casilla.constraints is not None
    assert "ley-35-2006:art-32-2015" in casilla.legal_refs
