"""A negative pago-fraccionado result stays deductible until a later quarter of the year uses it.

The AEAT instructions say Modelo 130 box 15 takes "los resultados negativos que, en su caso,
se hubieran obtenido en la casilla 19 de cualquiera de las autoliquidaciones anteriores [...]
del mismo ejercicio y que no hubieran sido deducidos anteriormente", never more than the
positive box 14. Modelo 131 says the same of its boxes 11, 15 and 10. So the carry into a
quarter is every earlier negative result less everything earlier quarters already deducted.

Figures, by hand from those instructions, with a minoracion of 100 each quarter:

    Cumulative income 150, 250, 3000, nothing withheld:
    1T: 03 150, 04 30, 07 30, 12 30, 14 -70, 15 0, 17 -70, 19 -70.
    2T: 03 250, 04 50, 05 30, 07 20, 12 20, 14 -80, 15 0, 17 -80, 19 -80.
    3T: 03 3000, 04 600, 05 50, 07 550, 12 550, 14 450, carry 70 + 80 = 150, 15 150, 17 300.

    Carry 150 against a smaller box 14 of 100 (cumulative income chosen so 07 is 200):
    3T: 14 100, 15 100, 17 0, leaving 50 for 4T.

These run the published formulas and the real previous-filing resolver.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from .....domain.calculations.registry.bindings_previous_filing import resolve_previous_filing_binding_values
from .....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_M130_CARRY = "modelo-130-resultados-negativos-anteriores"
_M131_CARRY = "modelo-131-resultados-negativos-anteriores"
_M130_INCOME = "modelo-130-actividad-economica-ingresos-cumulative"
_M130_EXPENSE = "modelo-130-actividad-economica-gastos-cumulative"
_M130_WITHHELD = "modelo-130-actividad-economica-retenciones-cumulative"
_M130_PRIOR_NET = "irpf.previous_year_economic_activity_net_income"
_M130_PRIOR_PAYMENTS = "modelo-130-pagos-fraccionados-anteriores"
_M131_AGRARIAN_VOLUME = "modelo-131-volumen-ingresos-agrario"


def _id(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="pago fraccionado carry test")


def _observation(modelo: str, period: str, result: RegistryCalculationResult) -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=modelo,
        filing_year=_YEAR,
        period=period,
        casilla_values=dict(result.values),
    )


_NORMAL_MODALITY = {"modelo-130-estimacion-directa-modalidad": "directa_normal"}


def _calculate(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    period: str,
    inputs: Mapping[str, Decimal],
    bindings: Mapping[str, Decimal],
    earlier: tuple[RegistryModeloObservation, ...],
) -> RegistryCalculationResult:
    snapshot = operation.snapshot(modelo, filing_year=_YEAR, period=period)
    resolved = resolve_previous_filing_binding_values(snapshot.revision, earlier, filing_year=_YEAR, period=period)
    carried = {_M130_CARRY: Decimal("0"), _M131_CARRY: Decimal("0"), _M130_PRIOR_PAYMENTS: Decimal("0")}
    binding_values = {**carried, **resolved, **bindings}
    binding_values = {key: value for key, value in binding_values.items() if _declares(snapshot, key)}
    return calculate_registry_snapshot(
        snapshot,
        inputs={
            **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
            **{_id(key): value for key, value in inputs.items()},
        },
        binding_values=binding_values,
        # These quarters model a normal-modality activity, whose box 02 carries no art. 30.2.ª provision.
        enum_binding_values={key: value for key, value in _NORMAL_MODALITY.items() if _declares(snapshot, key)},
        date_context={"filing_period": snapshot.revision.valid_from},
    )


def _declares(snapshot: RegistrySnapshot, binding_id: str) -> bool:
    return any(binding.id == binding_id for binding in snapshot.revision.bindings)


def _m130_quarter(
    operation: PinnedAuthorityOperation,
    period: str,
    *,
    income: str,
    earlier: tuple[RegistryModeloObservation, ...],
) -> RegistryCalculationResult:
    """Run one quarter on cumulative ``income``, no expense, no withholding, prior-year net income 5000."""
    return _calculate(
        operation,
        modelo="130",
        period=period,
        inputs={"08": Decimal("0"), "10": Decimal("0"), "16": Decimal("0"), "18": Decimal("0")},
        bindings={
            _M130_INCOME: Decimal(income),
            _M130_EXPENSE: Decimal("0"),
            _M130_WITHHELD: Decimal("0"),
            _M130_PRIOR_NET: Decimal("5000"),
            "modelo-130-casilla-06": Decimal("0"),
        },
        earlier=earlier,
    )


def _m130_chain(
    operation: PinnedAuthorityOperation, incomes: Mapping[str, str]
) -> dict[str, RegistryCalculationResult]:
    results: dict[str, RegistryCalculationResult] = {}
    earlier: list[RegistryModeloObservation] = []
    for period, income in incomes.items():
        result = _m130_quarter(operation, period, income=income, earlier=tuple(earlier))
        results[period] = result
        earlier.append(_observation("130", period, result))
    return results


def test_two_earlier_negatives_both_reach_box_15_of_modelo_130(operation: PinnedAuthorityOperation) -> None:
    """Box 15 takes 70 + 80, so 3T pays 300: the 1T negative is not lost when 2T is negative too."""
    results = _m130_chain(operation, {"1T": "150", "2T": "250", "3T": "3000"})

    assert results["1T"].values[_id("19")] == Decimal("-70.00")
    assert results["2T"].values[_id("19")] == Decimal("-80.00")
    assert results["3T"].values[_id("14")] == Decimal("450.00")
    assert results["3T"].values[_id("15")] == Decimal("150.00")
    assert results["3T"].values[_id("17")] == Decimal("300.00")


def test_what_box_14_could_not_absorb_still_reaches_the_next_quarter(operation: PinnedAuthorityOperation) -> None:
    """Carry 150 against box 14 of 100 uses 100; the other 50 reaches 4T instead of vanishing.

    3T cumulative income 1250 gives 04 250, 05 50, 07 200, 14 100. 4T cumulative income 3000
    gives 04 600, 05 250, 07 350, 14 250, so box 15 is the remaining 50 and box 17 is 200.
    """
    results = _m130_chain(operation, {"1T": "150", "2T": "250", "3T": "1250", "4T": "3000"})

    assert results["3T"].values[_id("15")] == Decimal("100.00")
    assert results["3T"].values[_id("17")] == Decimal("0.00")
    assert results["4T"].values[_id("14")] == Decimal("250.00")
    assert results["4T"].values[_id("15")] == Decimal("50.00")
    assert results["4T"].values[_id("17")] == Decimal("200.00")


def test_the_carry_reads_box_19_and_box_15_of_filed_quarters_alone(operation: PinnedAuthorityOperation) -> None:
    """A filing states its printed boxes; the carry needs nothing a form does not print."""
    snapshot = operation.snapshot("130", filing_year=_YEAR, period="3T")
    earlier = tuple(
        registry_grounded_modelo_observation(
            modelo="130",
            filing_year=_YEAR,
            period=period,
            casilla_values={_id("19"): result, _id("15"): deducted, _id("07"): Decimal("0")},
        )
        for period, result, deducted in (("1T", Decimal("-70"), Decimal("0")), ("2T", Decimal("-80"), Decimal("0")))
    )

    resolved = resolve_previous_filing_binding_values(snapshot.revision, earlier, filing_year=_YEAR, period="3T")

    assert resolved[_M130_CARRY] == Decimal("150")


def test_an_unknown_earlier_quarter_leaves_the_carry_unresolved(operation: PinnedAuthorityOperation) -> None:
    """With 2T never observed, 1T's negative alone would understate the carry: nothing is resolved."""
    snapshot = operation.snapshot("130", filing_year=_YEAR, period="3T")
    only_first = (
        registry_grounded_modelo_observation(
            modelo="130",
            filing_year=_YEAR,
            period="1T",
            casilla_values={_id("19"): Decimal("-70"), _id("15"): Decimal("0"), _id("07"): Decimal("0")},
        ),
    )

    resolved = resolve_previous_filing_binding_values(snapshot.revision, only_first, filing_year=_YEAR, period="3T")

    assert _M130_CARRY not in resolved


def test_the_first_quarter_has_nothing_to_carry(operation: PinnedAuthorityOperation) -> None:
    """No earlier quarter exists, so the carry is absent by design, not a resolved figure."""
    snapshot = operation.snapshot("130", filing_year=_YEAR, period="1T")

    assert _M130_CARRY not in resolve_previous_filing_binding_values(
        snapshot.revision, (), filing_year=_YEAR, period="1T"
    )


def test_the_end_of_period_balance_reports_what_later_quarters_can_still_deduct(
    operation: PinnedAuthorityOperation,
) -> None:
    """The working figure follows the running balance: 70, 150, then 50 after 3T used 100."""
    results = _m130_chain(operation, {"1T": "150", "2T": "250", "3T": "1250"})

    balance = _id("saldo-negativo-fin-periodo")
    assert [results[period].values[balance] for period in ("1T", "2T", "3T")] == [
        Decimal("70.00"),
        Decimal("150.00"),
        Decimal("50.00"),
    ]


def _m131_quarter(
    operation: PinnedAuthorityOperation,
    period: str,
    *,
    volume: str,
    withheld: str,
    earlier: tuple[RegistryModeloObservation, ...],
) -> RegistryCalculationResult:
    """Run one quarter: 2 % of ``volume`` less ``withheld``, nothing else on the form."""
    return _calculate(
        operation,
        modelo="131",
        period=period,
        inputs={
            "01": Decimal("0"),
            "02": Decimal("0"),
            "03": Decimal(volume),
            "05": Decimal("0"),
            "08": Decimal(withheld),
            "09": Decimal("0"),
            "12": Decimal("0"),
            "14": Decimal("0"),
        },
        bindings={_M131_AGRARIAN_VOLUME: Decimal("0")},
        earlier=earlier,
    )


def _m131_chain(
    operation: PinnedAuthorityOperation, quarters: Mapping[str, tuple[str, str]]
) -> dict[str, RegistryCalculationResult]:
    results: dict[str, RegistryCalculationResult] = {}
    earlier: list[RegistryModeloObservation] = []
    for period, (volume, withheld) in quarters.items():
        result = _m131_quarter(operation, period, volume=volume, withheld=withheld, earlier=tuple(earlier))
        results[period] = result
        earlier.append(_observation("131", period, result))
    return results


def test_two_earlier_negatives_both_reach_box_11_of_modelo_131(operation: PinnedAuthorityOperation) -> None:
    """2 % of 10000 is 200: 1T -100 and 2T -50 both carry, so 3T with box 10 of 400 pays 250."""
    results = _m131_chain(
        operation,
        {"1T": ("10000", "300"), "2T": ("10000", "250"), "3T": ("20000", "0")},
    )

    assert results["1T"].values[_id("15")] == Decimal("-100.00")
    assert results["2T"].values[_id("15")] == Decimal("-50.00")
    assert results["3T"].values[_id("10")] == Decimal("400.00")
    assert results["3T"].values[_id("11")] == Decimal("150.00")
    assert results["3T"].values[_id("13")] == Decimal("250.00")


def test_box_11_of_modelo_131_never_exceeds_the_positive_box_10(operation: PinnedAuthorityOperation) -> None:
    """Carry 200 against box 10 of 80 uses 80, leaving 13 at 0 and 120 for the next quarter.

    Instructions, box 11: "en ningun caso podra figurar en la casilla 11 un importe superior a
    la cantidad positiva consignada en la casilla 10".
    """
    results = _m131_chain(
        operation,
        {"1T": ("10000", "400"), "2T": ("4000", "0"), "3T": ("10000", "0")},
    )

    assert results["2T"].values[_id("10")] == Decimal("80.00")
    assert results["2T"].values[_id("11")] == Decimal("80.00")
    assert results["2T"].values[_id("13")] == Decimal("0.00")
    assert results["3T"].values[_id("11")] == Decimal("120.00")
    assert results["3T"].values[_id("13")] == Decimal("80.00")


def test_box_11_of_modelo_131_stays_zero_while_box_10_is_negative(operation: PinnedAuthorityOperation) -> None:
    """Box 11 applies only "si en la casilla 10 anterior se hubiera obtenido una cantidad positiva"."""
    results = _m131_chain(operation, {"1T": ("10000", "300"), "2T": ("10000", "250")})

    assert results["2T"].values[_id("11")] == Decimal("0.00")
    assert results["2T"].values[_id("13")] == Decimal("-50.00")
    assert results["2T"].values[_id("15")] == Decimal("-50.00")
