"""Borrador participation: snapshot admission and the value the borrador may supply are two typed facts.

Each refusal is driven against an isolated fixture holding exactly one defect,
beside a clean twin that passes, so a check that stopped looking fails here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.casilla_id import validated_casilla_id
from ..binding_borrador_participation import BorradorParticipation
from ..binding_provider_registration import validate_binding_against_registration
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..retencion_soportada_bindings import credit_borrador_participation_failures
from ..schema import BindingDefinition, FormulaDefinition
from ..schema_formula import FormulaExpression
from ..schema_input_kind import InputKind
from .referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    minimal_revision,
    segmented_casilla,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CREDIT = validated_casilla_id("0596")
_OTHER_CREDIT = validated_casilla_id("0602")
_TOTAL = validated_casilla_id("0609")
_INCOME = validated_casilla_id("0012")
_FAMILY_ID = "test-retencion-soportada-trabajo"
_MANUAL_ID = "test-manual-credit"

_FAMILY_PROVIDER: dict[str, object] = {
    "kind": "retencion_soportada",
    "income_class": "trabajo",
    "quantity": "pago_a_cuenta",
}
_LEDGER_PROVIDER: dict[str, object] = {
    "kind": "ledger_renta_income_aggregation",
    "modelo": "100",
    "target_casilla_id": "0171",
    "fact": "declared_withheld_amount_sum",
}


def _binding(
    binding_id: str,
    provider: dict[str, object],
    *,
    aeat_prefilled: bool = True,
    participation: str | None = "cross_check_only",
) -> BindingDefinition:
    return BindingDefinition.model_validate(
        {
            "id": binding_id,
            "provider": provider,
            "value": BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.DECIMAL),
            "aggregation": {"op": "sum" if provider["kind"] != "manual_input" else "copy"},
            "legal_refs": (REFERENCE_LEGAL_ID,),
            "source_refs": (REFERENCE_SOURCE_ID,),
            "aeat_prefilled": aeat_prefilled,
            **({} if participation is None else {"borrador_participation": participation}),
        },
    )


def _manual(casilla: str, *, participation: str | None) -> BindingDefinition:
    return _binding(
        _MANUAL_ID,
        {"kind": "manual_input", "casilla_id": casilla, "data_type": "money"},
        participation=participation,
    )


def _casilla(casilla_id: str, role: str, *, binding: str | None = None, computed: bool = False):
    update: dict[str, object] = {"semantic_role": role}
    if binding is not None:
        update.update(input_kind=InputKind.BOUND, binding=binding)
    if computed:
        update.update(input_kind=InputKind.COMPUTED, formula="test.total-pagos")
    return segmented_casilla(validated_casilla_id(casilla_id), casilla_id, None).model_copy(update=update)


def _revision(*bindings: BindingDefinition, bound: dict[str, str]):
    total = FormulaDefinition(
        id="test.total-pagos",
        target_casilla_id=_TOTAL,
        expression=FormulaExpression(
            op="add",
            args=(FormulaExpression(casilla_id=_CREDIT), FormulaExpression(casilla_id=_OTHER_CREDIT)),
        ),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    casillas = (
        _casilla("0596", "irpf_retencion_trabajo", binding=bound.get("0596")),
        _casilla("0602", "irpf_ingreso_cuenta_art_92_8", binding=bound.get("0602")),
        _casilla("0012", "irpf_rendimiento_trabajo", binding=bound.get("0012")),
        _casilla("0609", "irpf_total_pagos_cuenta", computed=True),
    )
    return minimal_revision(casillas=casillas, formulas=(total,), bindings=bindings)


def test_an_undeclared_participation_supplies_the_value_and_cross_check_only_does_not() -> None:
    assert _manual("0012", participation=None).borrador_supplies_value
    assert _manual("0012", participation="precedence").borrador_supplies_value
    cross_check = _manual("0012", participation="cross_check_only")
    assert cross_check.borrador_participation is BorradorParticipation.CROSS_CHECK_ONLY
    assert not cross_check.borrador_supplies_value
    assert not _manual("0012", participation=None).model_copy(update={"aeat_prefilled": False}).borrador_supplies_value


def test_a_participation_on_a_binding_no_snapshot_may_hold_is_refused() -> None:
    with pytest.raises(ValidationError, match="not aeat_prefilled"):
        _binding(_FAMILY_ID, _FAMILY_PROVIDER, aeat_prefilled=False)
    assert _binding(_FAMILY_ID, _FAMILY_PROVIDER, aeat_prefilled=False, participation=None).aeat_prefilled is False


def test_an_unknown_participation_token_is_refused() -> None:
    with pytest.raises(ValidationError, match="cross_check"):
        _manual("0012", participation="cross_check")


def test_a_computed_kind_may_be_held_for_comparison_but_never_supply_the_value() -> None:
    held = _binding("test-ledger", _LEDGER_PROVIDER)
    assert validate_binding_against_registration(held) == ()
    supplying = _binding("test-ledger", _LEDGER_PROVIDER, participation="precedence")
    (diagnostic,) = validate_binding_against_registration(supplying)
    assert "borrador precedence" in diagnostic


def test_a_family_credit_binding_held_for_comparison_passes_the_build() -> None:
    revision = _revision(_binding(_FAMILY_ID, _FAMILY_PROVIDER), bound={"0596": _FAMILY_ID})
    assert credit_borrador_participation_failures(revision) == ()
    assert validate_binding_against_registration(revision.bindings[0]) == ()


@pytest.mark.parametrize("participation", ["precedence", None])
def test_a_credit_casilla_the_borrador_may_supply_is_refused(participation: str | None) -> None:
    """Undeclared participation reads as precedence, so it is refused on a credit the same way."""
    revision = _revision(_manual("0602", participation=participation), bound={"0602": _MANUAL_ID})
    (failure,) = credit_borrador_participation_failures(revision)
    assert _MANUAL_ID in failure and "'0602'" in failure


def test_a_credit_reached_through_a_formula_operand_is_refused_too() -> None:
    supplying = _manual("0602", participation="precedence")
    revision = _revision(supplying, bound={})
    feeding = FormulaDefinition(
        id="test.credit-from-binding",
        target_casilla_id=_OTHER_CREDIT,
        expression=FormulaExpression(binding=_MANUAL_ID),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = revision.model_copy(update={"formulas": (*revision.formulas, feeding)})
    (failure,) = credit_borrador_participation_failures(revision)
    assert "'0602'" in failure


def test_a_borrador_value_outside_the_credit_set_keeps_its_precedence() -> None:
    revision = _revision(_manual("0012", participation="precedence"), bound={"0012": _MANUAL_ID})
    assert credit_borrador_participation_failures(revision) == ()
