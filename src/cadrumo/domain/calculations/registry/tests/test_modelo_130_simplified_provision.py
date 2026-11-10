"""Modelo 130 box 02 carries the simplified-modality provision of RIRPF art. 30.2.ª.

The instructions for box 02: under the simplified modality "se incluirán en esta casilla los
importes de las amortizaciones, de las provisiones deducibles y de los gastos de difícil
justificación correspondientes al período comprendido entre el primer día del año y el último
día del trimestre, determinados conforme a las especialidades establecidas en el artículo 30 del
Reglamento". Article 30.2.ª sets that provision at 5 per cent of the net income "excluido este
concepto", at most 2.000 euros a year; LIRPF disposición adicional quincuagésima sexta raises the
percentage to 7 per cent for the período impositivo 2023. Every figure below is worked by hand
from those texts, never read from a run.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from .....core.casilla_id import validated_casilla_id_map
from .....core.period import Period
from .....domain.period import calculation_filing_date
from ..authority import PinnedAuthorityOperation
from ..formula_runtime import calculate_registry_snapshot
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

# A year with the ordinary 5 per cent provision.
_YEAR = filing_year_envelope().horizon
_MODALITY = "modelo-130-estimacion-directa-modalidad"
_PRIOR_EXPENSES = "gastos-deducibles-previos"
_PROVISION = "provisiones-gastos-dificil-justificacion"
_SIMPLIFIED = "directa_simplificada"
_NORMAL = "directa_normal"


def _boxes(
    operation: PinnedAuthorityOperation,
    *,
    year: int,
    period: str,
    income: str,
    expenses: str,
    modality: str | None = _SIMPLIFIED,
    withholding: str = "0",
    prior_payments: str = "0",
    declare_unresolved: bool = False,
) -> dict[str, Decimal]:
    """Calculate one quarter through the published registry, the way the work calculation does."""
    enum_bindings = {} if modality is None else {_MODALITY: modality}
    result = calculate_registry_snapshot(
        operation.snapshot("130", filing_year=year, period=period),
        inputs=validated_casilla_id_map(
            {"01": Decimal(income), _PRIOR_EXPENSES: Decimal(expenses), "06": Decimal(withholding)},
            surface="art. 30.2 provision test inputs",
        ),
        date_context={"filing_period": calculation_filing_date(Period.from_year_and_code(year, period))},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("100000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal(prior_payments),
        },
        enum_binding_values=enum_bindings,
        unresolved_binding_ids=(_MODALITY,) if declare_unresolved else (),
    )
    return {str(entry.target_casilla_id): entry.value for entry in result.entries}


# The cumulative quarters of a simplified-modality autonomo, by hand (2025, 5 per cent):
#   1T  4.000 -   500 = 3.500 x 5 % = 175  -> box 02   675, box 03 3.325, 20 % = 665,   - 0   - 600   = 65
#   2T  7.500 - 1.200 = 6.300 x 5 % = 315  -> box 02 1.515, box 03 5.985, 20 % = 1.197, - 65  - 1.125 = 7
#   3T  9.500 - 1.500 = 8.000 x 5 % = 400  -> box 02 1.900, box 03 7.600, 20 % = 1.520, - 72  - 1.265 = 183
#   4T 12.000 - 2.400 = 9.600 x 5 % = 480  -> box 02 2.880, box 03 9.120, 20 % = 1.824, - 255 - 1.440 = 129
_SIMPLIFIED_QUARTERS = (
    ("1T", "4000", "500", "600", "0", "175.00", "675.00", "3325.00", "65.00"),
    ("2T", "7500", "1200", "1125", "65", "315.00", "1515.00", "5985.00", "7.00"),
    ("3T", "9500", "1500", "1265", "72", "400.00", "1900.00", "7600.00", "183.00"),
    ("4T", "12000", "2400", "1440", "255", "480.00", "2880.00", "9120.00", "129.00"),
)


@pytest.mark.parametrize(
    ("period", "income", "expenses", "withholding", "prior", "provision", "box_02", "box_03", "box_07"),
    _SIMPLIFIED_QUARTERS,
)
def test_each_simplified_quarter_adds_the_provision_to_box_02(
    *,
    operation: PinnedAuthorityOperation,
    period: str,
    income: str,
    expenses: str,
    withholding: str,
    prior: str,
    provision: str,
    box_02: str,
    box_03: str,
    box_07: str,
) -> None:
    boxes = _boxes(
        operation,
        year=_YEAR,
        period=period,
        income=income,
        expenses=expenses,
        withholding=withholding,
        prior_payments=prior,
    )

    assert boxes[_PROVISION] == Decimal(provision), boxes
    assert boxes["02"] == Decimal(box_02), boxes
    assert boxes["03"] == Decimal(box_03), boxes
    assert boxes["07"] == Decimal(box_07), boxes


def test_the_annual_cap_binds_the_cumulative_provision(*, operation: PinnedAuthorityOperation) -> None:
    """50.000 - 10.000 = 40.000 x 5 % = 2.000 exactly; 60.000 - 10.000 = 50.000 x 5 % = 2.500, held to 2.000."""
    at_cap = _boxes(operation, year=_YEAR, period="3T", income="50000", expenses="10000")
    above_cap = _boxes(operation, year=_YEAR, period="4T", income="60000", expenses="10000")

    assert at_cap[_PROVISION] == Decimal("2000.00"), at_cap
    assert above_cap[_PROVISION] == Decimal("2000.00"), above_cap
    assert above_cap["02"] == Decimal("12000.00"), above_cap
    assert above_cap["03"] == Decimal("48000.00"), above_cap


def test_a_negative_prior_net_income_has_no_provision(*, operation: PinnedAuthorityOperation) -> None:
    """1.000 - 3.000 = -2.000: there is no positive net income to take 5 per cent of."""
    boxes = _boxes(operation, year=_YEAR, period="1T", income="1000", expenses="3000")

    assert boxes[_PROVISION] == Decimal("0.00"), boxes
    assert boxes["02"] == Decimal("3000.00"), boxes
    assert boxes["03"] == Decimal("-2000.00"), boxes
    assert boxes["04"] == Decimal("0.00"), boxes


@pytest.mark.parametrize(
    ("year", "period", "provision", "box_02"),
    (
        # 3.500 x 5 % = 175 in every year but 2023, where 3.500 x 7 % = 245.
        (2022, "4T", "175.00", "675.00"),
        (2023, "1T", "245.00", "745.00"),
        (2023, "4T", "245.00", "745.00"),
        (2024, "1T", "175.00", "675.00"),
        (2026, "2T", "175.00", "675.00"),
    ),
)
def test_the_percentage_is_seven_per_cent_only_for_2023(
    *, operation: PinnedAuthorityOperation, year: int, period: str, provision: str, box_02: str
) -> None:
    boxes = _boxes(operation, year=year, period=period, income="4000", expenses="500")

    assert boxes[_PROVISION] == Decimal(provision), boxes
    assert boxes["02"] == Decimal(box_02), boxes


def test_the_2023_cap_is_still_two_thousand_euros(*, operation: PinnedAuthorityOperation) -> None:
    """40.000 - 10.000 = 30.000 x 7 % = 2.100, held to 2.000."""
    boxes = _boxes(operation, year=2023, period="4T", income="40000", expenses="10000")

    assert boxes[_PROVISION] == Decimal("2000.00"), boxes


def test_the_normal_modality_has_no_provision(*, operation: PinnedAuthorityOperation) -> None:
    """The normal modality deducts its expenses as they are: box 02 = 500, box 03 = 3.500, 20 % = 700."""
    boxes = _boxes(operation, year=_YEAR, period="1T", income="4000", expenses="500", modality=_NORMAL)

    assert boxes[_PROVISION] == Decimal("0.00"), boxes
    assert boxes["02"] == Decimal("500.00"), boxes
    assert boxes["03"] == Decimal("3500.00"), boxes
    assert boxes["04"] == Decimal("700.00"), boxes


@pytest.mark.parametrize("declare_unresolved", (False, True))
def test_an_undeclared_modality_leaves_box_02_unresolved(
    *, operation: PinnedAuthorityOperation, declare_unresolved: bool
) -> None:
    """Without the modality the provision is unknown, so box 02 and everything after it stay unresolved.

    A profile that never recorded its modality supplies no value at all; that is the same unknown
    as a resolver that ran and reported the binding unresolved, never a malformed formula operand.
    """
    boxes: Mapping[str, Decimal] = _boxes(
        operation,
        year=_YEAR,
        period="1T",
        income="4000",
        expenses="500",
        modality=None,
        declare_unresolved=declare_unresolved,
    )

    assert _PROVISION not in boxes, boxes
    assert "02" not in boxes, boxes
    assert "03" not in boxes, boxes
    assert "07" not in boxes, boxes
