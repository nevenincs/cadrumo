"""Box 0670 of the Modelo 100, the result of the return, is calculated in every supported ejercicio.

Each approving order prints the box as the cuota diferencial (0610) less the
deductions the taxpayer applies and plus the advance payments to regularise.
An edition that declares the maternity-deduction catch-up rows (Orden
HFP/310/2023: "Incremento de la deducción" and "Incremento por gastos en
guarderías", amounts not applied in earlier ejercicios) subtracts every one
of them, so each lowers the result by exactly its own amount. The ejercicios
come from the registry's support envelope and the catch-up rows from the
section each revision declares, never from a list here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..schema import RegistrySnapshot
from ..schema_base import CasillaDataType
from ..schema_input_kind import InputKind
from .authored_editions import supported_authored_exercises
from .modelo_100_registry_support import neutral_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SALARY: CasillaId = validated_casilla_id("0003", surface="_SALARY")
_RESULT_OF_THE_RETURN: CasillaId = validated_casilla_id("0670", surface="_RESULT_OF_THE_RETURN")
_CATCH_UP_SECTION = "ampliacion_deduc_mater_res"
_CATCH_UP_AMOUNT = Decimal("100.00")


def _snapshot(registry_snapshot: Callable[..., RegistrySnapshot], year: int) -> RegistrySnapshot:
    return registry_snapshot("100", year, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _calculate(
    snapshot: RegistrySnapshot, year: int, inputs: Mapping[CasillaId, Decimal] | None = None
) -> RegistryCalculationResult:
    decimals, booleans, dates, enums = neutral_binding_values(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    booleans["renta-modelo-100-estimacion-directa-es-normal"] = True
    decimals |= {"renta-profile-declaration-type": Decimal(1)}
    return calculate_registry_snapshot(
        snapshot,
        inputs={
            _SALARY: Decimal("30000.00"),
            **(inputs or {}),
            **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimals),
        },
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )


def _catch_up_rows(snapshot: RegistrySnapshot) -> tuple[CasillaId, ...]:
    return tuple(
        casilla.id
        for casilla in snapshot.revision.casillas
        if _CATCH_UP_SECTION in casilla.section and casilla.data_type is CasillaDataType.MONEY
    )


def _editions_with_catch_up_rows(registry_snapshot: Callable[..., RegistrySnapshot]) -> list[int]:
    return [year for year in supported_authored_exercises("100") if _catch_up_rows(_snapshot(registry_snapshot, year))]


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_every_edition_calculates_the_result_of_the_return(
    registry_snapshot: Callable[..., RegistrySnapshot], year: int
) -> None:
    snapshot = _snapshot(registry_snapshot, year)
    casilla = next(item for item in snapshot.revision.casillas if item.id == _RESULT_OF_THE_RETURN)
    assert casilla.input_kind is InputKind.COMPUTED
    assert casilla.formula == "renta-resultado-declaracion"

    result = _calculate(snapshot, year)

    assert _RESULT_OF_THE_RETURN in result.values
    assert all(outcome.casilla_id != _RESULT_OF_THE_RETURN for outcome in result.unresolved_outcomes)


def test_some_supported_edition_declares_the_catch_up_rows(registry_snapshot: Callable[..., RegistrySnapshot]) -> None:
    assert _editions_with_catch_up_rows(registry_snapshot)


def test_each_catch_up_row_lowers_the_result_by_its_own_amount(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    for year in _editions_with_catch_up_rows(registry_snapshot):
        snapshot = _snapshot(registry_snapshot, year)
        baseline = _calculate(snapshot, year).values[_RESULT_OF_THE_RETURN]
        for row in _catch_up_rows(snapshot):
            result = _calculate(snapshot, year, {row: _CATCH_UP_AMOUNT})
            assert result.values[_RESULT_OF_THE_RETURN] == baseline - _CATCH_UP_AMOUNT, (year, row)
