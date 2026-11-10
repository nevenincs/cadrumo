"""Box 0700 of the newest authored Modelo 100 is the declared amount payable or refundable, derived from 0670 or 0695.

The official record design names the element RESINGDEV "Resultado a ingresar o
a devolver (casilla [0670] o casilla [0695] de la declaración)". The box is the
result of the return unless the spouse compensation suspends part of an amount
payable, in which case it is the remainder payable. A refund waived for that
compensation has no registry formula for its remainder, so only this box is
left without a value, for a typed reason, and never stated as an amount; every
other box still calculates.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ..ids import BindingId
from ..schema import RegistrySnapshot
from ..schema_input_kind import InputKind
from .authored_editions import newest_authored_edition
from .modelo_100_registry_support import neutral_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = newest_authored_edition("100")
_SALARY: CasillaId = validated_casilla_id("0003", surface="_SALARY")
_RESULT_OF_THE_RETURN: CasillaId = validated_casilla_id("0670", surface="_RESULT_OF_THE_RETURN")
_SUSPENDED_PAYABLE: CasillaId = validated_casilla_id("0693", surface="_SUSPENDED_PAYABLE")
_WAIVED_REFUND: CasillaId = validated_casilla_id("0694", surface="_WAIVED_REFUND")
_REMAINDER: CasillaId = validated_casilla_id("0695", surface="_REMAINDER")
_AMOUNT_PAYABLE_OR_REFUNDABLE: CasillaId = validated_casilla_id("0700", surface="_AMOUNT_PAYABLE_OR_REFUNDABLE")
_WITHHELD_ON_EMPLOYMENT: BindingId = "renta-retencion-soportada-trabajo"


@pytest.fixture
def snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """The newest authored edition at calculation grade: these tests assert the derivation, never filing eligibility."""
    return registry_snapshot("100", _YEAR, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _calculate(
    snapshot: RegistrySnapshot,
    *,
    withheld: Decimal = Decimal(0),
    inputs: dict[CasillaId, Decimal] | None = None,
) -> RegistryCalculationResult:
    decimals, booleans, dates, enums = neutral_binding_values(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    booleans["renta-modelo-100-estimacion-directa-es-normal"] = True
    decimals |= {
        "renta-profile-declaration-type": Decimal(1),
        _WITHHELD_ON_EMPLOYMENT: withheld,
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs={
            _SALARY: Decimal("30000.00"),
            **(inputs or {}),
            **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimals),
        },
        date_context={"filing_period": date(_YEAR, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )


def test_the_edition_declares_the_box_as_calculated_from_the_result_and_the_remainder(
    snapshot: RegistrySnapshot,
) -> None:
    """The box is computed by its own formula; it is no longer an optional value the filer types."""
    casilla = next(item for item in snapshot.revision.casillas if item.id == _AMOUNT_PAYABLE_OR_REFUNDABLE)
    assert casilla.input_kind is InputKind.COMPUTED
    assert casilla.formula == "renta-resultado-ingresar-o-devolver"


def test_without_compensation_the_box_is_the_amount_payable_of_the_return(snapshot: RegistrySnapshot) -> None:
    result = _calculate(snapshot)

    assert result.values[_RESULT_OF_THE_RETURN] > 0
    assert result.values[_AMOUNT_PAYABLE_OR_REFUNDABLE] == result.values[_RESULT_OF_THE_RETURN]


def test_without_compensation_a_refund_keeps_its_negative_sign(snapshot: RegistrySnapshot) -> None:
    result = _calculate(snapshot, withheld=Decimal("20000.00"))

    assert result.values[_RESULT_OF_THE_RETURN] < 0
    assert result.values[_AMOUNT_PAYABLE_OR_REFUNDABLE] == result.values[_RESULT_OF_THE_RETURN]


def test_a_suspended_payable_makes_the_box_the_remainder_payable(snapshot: RegistrySnapshot) -> None:
    suspended = Decimal("200.00")
    result = _calculate(snapshot, inputs={_SUSPENDED_PAYABLE: suspended})

    assert result.values[_REMAINDER] == result.values[_RESULT_OF_THE_RETURN] - suspended
    assert result.values[_AMOUNT_PAYABLE_OR_REFUNDABLE] == result.values[_REMAINDER]
    assert result.values[_AMOUNT_PAYABLE_OR_REFUNDABLE] != result.values[_RESULT_OF_THE_RETURN]


def test_a_waived_refund_leaves_only_the_box_unresolved_for_a_typed_reason(snapshot: RegistrySnapshot) -> None:
    result = _calculate(snapshot, withheld=Decimal("20000.00"), inputs={_WAIVED_REFUND: Decimal("100.00")})

    assert _AMOUNT_PAYABLE_OR_REFUNDABLE not in result.values
    (outcome,) = result.unresolved_outcomes
    assert outcome.casilla_id == _AMOUNT_PAYABLE_OR_REFUNDABLE
    assert outcome.reason is RegistryUnresolvedOutcomeReason.WAIVED_REFUND_RESULT_UNSUPPORTED
    assert outcome.formula_id == "renta-resultado-ingresar-o-devolver"
    assert outcome.operand_casilla_refs == (_WAIVED_REFUND,)
    assert result.values[_WAIVED_REFUND] == Decimal("100.00")
    assert result.values[_RESULT_OF_THE_RETURN] < 0
    assert (
        result.values[_RESULT_OF_THE_RETURN]
        == _calculate(snapshot, withheld=Decimal("20000.00")).values[_RESULT_OF_THE_RETURN]
    )
