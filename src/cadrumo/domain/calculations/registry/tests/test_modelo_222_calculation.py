"""Modelo 222 pago fraccionado computed through the real registry calculation engine.

Every expected value below is worked by hand from the formulas printed in the
AEAT instructions for 2025 and later (``aeat-modelo-222-instructions``), not
read back from the registry: the arithmetic is shown beside each assertion so a
reader can check it against the instructions without running the engine.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..formula_runtime import calculate_registry_snapshot
from ..schema import RegistrySnapshot
from ._cross_dependency_calculation_support import _casilla_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FORMULA_TARGETS = frozenset({"03", "10", "13", "16", "18", "19", "22", "25", "26", "32", "34", "38", "39", "63", "66"})
_MANUAL_BOXES = (
    "01", "02", "04", "05", "06", "07", "08", "11", "12", "14", "15", "17", "20", "21", "23", "24",
    "27", "28", "29", "30", "31", "33", "37", "42", "43", "44", "45", "46", "47", "48", "49", "50",
    "51", "52", "53", "54", "55", "56", "57", "58", "59", "60", "61", "62", "64", "65", "67",
)  # fmt: skip


def _calculate(
    registry_snapshot: Callable[..., RegistrySnapshot],
    values: Mapping[str, str],
) -> dict[str, Decimal]:
    snapshot = registry_snapshot("222", 2025, "1P", grade=RegistryAuthorityGrade.CALCULATION)
    assert {formula.target_casilla_id for formula in snapshot.revision.formulas} == _FORMULA_TARGETS
    inputs = _casilla_inputs({box: Decimal(values.get(box, "0")) for box in _MANUAL_BOXES})
    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context={"filing_period": date(2025, 4, 20)})
    return {entry.target_casilla_id: entry.value for entry in result.entries}


def test_modalidad_40_3_single_rate_group_reaches_the_cantidad_a_ingresar(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    computed = _calculate(
        registry_snapshot,
        {
            "04": "100000", "05": "20000", "07": "5000", "06": "10000", "37": "2000", "08": "3000",
            "11": "4000", "12": "1000", "14": "3000", "17": "24",
            "49": "300", "50": "200", "51": "1000", "58": "100",
            "27": "500", "28": "1500", "29": "100", "30": "5000", "33": "12000",
        },
    )  # fmt: skip

    assert computed["38"] == Decimal("25000")  # 20000 + 0 + 5000
    assert computed["39"] == Decimal("15000")  # 10000 + 2000 + 3000
    assert computed["10"] == Decimal("110000")  # 100000 + 25000 - 15000 + 0 - 0
    assert computed["13"] == Decimal("113000")  # 110000 + 4000 - 1000
    assert computed["16"] == Decimal("110000")  # 113000 - 3000
    # 110000 x 24 / 100 + 300 + 200 - 1000 - 100. The diseno de registro's label
    # would subtract [49] and [50] and omit [58], giving 24900; the instructions
    # govern the computation.
    assert computed["18"] == Decimal("25800")
    assert computed["26"] == Decimal("0")  # the several-rates lane is left empty
    assert computed["32"] == Decimal("18800")  # (25800 + 0 - 500 - 1500) x 100 / 100 - 5000 - 0
    assert computed["34"] == Decimal("18800")  # the greater of 18800 and the 12000 minimum
    assert computed["03"] == Decimal("0")  # the 40.2 lane is left empty


def test_modalidad_40_3_several_rates_group_sums_its_tramos(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    computed = _calculate(
        registry_snapshot,
        {
            "20": "50000", "21": "24", "23": "30000", "24": "19", "61": "10000", "62": "15", "64": "1000", "65": "10",
            "54": "100", "42": "400", "29": "80", "30": "1000", "33": "20000",
        },
    )  # fmt: skip

    assert computed["19"] == Decimal("91000")  # 50000 + 30000 + 10000 + 1000
    assert computed["22"] == Decimal("12000")  # 50000 x 24 / 100
    assert computed["25"] == Decimal("5700")  # 30000 x 19 / 100
    assert computed["63"] == Decimal("1500")  # 10000 x 15 / 100
    assert computed["66"] == Decimal("100")  # 1000 x 10 / 100
    assert computed["26"] == Decimal("19000")  # 12000 + 5700 + 1500 + 100 + 100 - 400
    assert computed["32"] == Decimal("14200")  # 19000 x 80 / 100 - 1000
    assert computed["34"] == Decimal("20000")  # the 20000 minimum exceeds the 14200 result


def test_bases_and_resultado_previo_the_instructions_bar_from_going_negative_stop_at_zero(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    computed = _calculate(
        registry_snapshot,
        {"04": "1000", "14": "5000", "17": "24", "21": "24", "20": "1000", "42": "900"},
    )

    assert computed["13"] == Decimal("1000")
    assert computed["16"] == Decimal("0")  # 1000 - 5000 is negative, "sin poder ser negativa"
    assert computed["22"] == Decimal("240")
    assert computed["26"] == Decimal("0")  # 240 - 900 is negative, "no puede ser negativo"


def test_modalidad_40_2_applies_eighteen_percent_less_a_prior_complementaria(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    computed = _calculate(registry_snapshot, {"01": "10000.05", "02": "500"})

    assert computed["03"] == Decimal("1300.01")  # 10000.05 x 18% = 1800.009, to the cent, less 500
