"""The suffered-withholding binding family: closed vocabulary, registration and revision checks.

Each check is driven against an isolated fixture holding exactly one defect, so
a validator that stopped looking would let the fixture through and fail here.
The clean fixture must pass every check, or the defective ones prove nothing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .....core.casilla_id import validated_casilla_id
from .....core.retencion_soportada import RetencionSoportadaCantidad, RetencionSoportadaClase
from ..binding_provider_registration import (
    RouteOwnership,
    registration_for,
    validate_binding_against_registration,
)
from ..binding_terminal_origin import TerminalOriginClass
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..retencion_soportada_bindings import (
    RETENCION_SOPORTADA_CREDIT_ROLES,
    RETENCION_SOPORTADA_INCOME_ROLES,
    RetencionSoportadaProvider,
    credit_casilla_ids,
    retencion_soportada_revision_failures,
    revision_declares_retencion_soportada,
)
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

_TRABAJO_CASILLA = validated_casilla_id("0596")
_CAPITAL_CASILLA = validated_casilla_id("0597")
_OUTSIDE_CASILLA = validated_casilla_id("0598")
_TOTAL_CASILLA = validated_casilla_id("0609")
_BINDING_ID = "renta-retencion-soportada-trabajo"


def _binding(
    *,
    income_class: str = "trabajo",
    quantity: str = "pago_a_cuenta",
    data_type: BindingDataType = BindingDataType.MONEY,
    channel: BindingValueChannel = BindingValueChannel.DECIMAL,
    op: BindingAggregationOp | None = None,
) -> BindingDefinition:
    return BindingDefinition(
        id=_BINDING_ID,
        provider={"kind": "retencion_soportada", "income_class": income_class, "quantity": quantity},
        value=BindingValueContract(data_type=data_type, channel=channel),
        aggregation=None if op is None else BindingAggregation(op=op),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )


def _casilla(casilla_id: str, role: str, *, bound: bool = False, computed: bool = False):
    update: dict[str, object] = {"semantic_role": role}
    if bound:
        update.update(input_kind=InputKind.BOUND, binding=_BINDING_ID)
    if computed:
        update.update(input_kind=InputKind.COMPUTED, formula="test.total-pagos")
    return segmented_casilla(validated_casilla_id(casilla_id), casilla_id, None).model_copy(update=update)


def _total_formula() -> FormulaDefinition:
    return FormulaDefinition(
        id="test.total-pagos",
        target_casilla_id=_TOTAL_CASILLA,
        expression=FormulaExpression(
            op="add",
            args=(FormulaExpression(casilla_id=_TRABAJO_CASILLA), FormulaExpression(casilla_id=_CAPITAL_CASILLA)),
        ),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )


def _revision(*, binding: BindingDefinition, bound_casilla: str = "0596", bound_role: str = "irpf_retencion_trabajo"):
    casillas = [
        _casilla("0596", "irpf_retencion_trabajo", bound=bound_casilla == "0596"),
        _casilla("0597", "irpf_retencion_capital_mobiliario"),
        _casilla("0609", "irpf_total_pagos_cuenta", computed=True),
    ]
    if bound_casilla == "0596":
        casillas[0] = _casilla("0596", bound_role, bound=True)
    else:
        casillas.append(_casilla(bound_casilla, bound_role, bound=True))
    return minimal_revision(casillas=tuple(casillas), formulas=(_total_formula(),), bindings=(binding,))


def test_the_income_class_vocabulary_is_the_twelve_credit_classes() -> None:
    assert len(RetencionSoportadaClase) == 12
    assert set(RETENCION_SOPORTADA_CREDIT_ROLES) == set(RetencionSoportadaClase)


def test_an_unknown_income_class_is_refused_at_the_provider() -> None:
    with pytest.raises(ValidationError):
        RetencionSoportadaProvider.model_validate(
            {"kind": "retencion_soportada", "income_class": "rendimiento_desconocido", "quantity": "pago_a_cuenta"},
        )
    with pytest.raises(ValidationError):
        RetencionSoportadaProvider.model_validate(
            {"kind": "retencion_soportada", "income_class": "trabajo", "quantity": "retencion_neta"},
        )


def test_the_provider_reads_a_known_class_and_quantity() -> None:
    provider = RetencionSoportadaProvider.model_validate(
        {"kind": "retencion_soportada", "income_class": "capital_mobiliario", "quantity": "pago_a_cuenta"},
    )
    assert provider.income_class is RetencionSoportadaClase.CAPITAL_MOBILIARIO
    assert provider.quantity is RetencionSoportadaCantidad.PAGO_A_CUENTA


def test_the_registration_is_filing_grade_on_payer_certificate_operator_input_and_profile_field() -> None:
    registration = registration_for(BindingSourceKind.RETENCION_SOPORTADA)
    assert registration.disposition == "filing_grade"
    assert registration.permitted_terminal_origins == frozenset(
        {TerminalOriginClass.PAYER_CERTIFICATE, TerminalOriginClass.OPERATOR_INPUT, TerminalOriginClass.PROFILE_FIELD},
    )
    assert TerminalOriginClass.PERCEPTOR_OBSERVATION not in registration.permitted_terminal_origins
    assert registration.permitted_aggregation_ops == frozenset({BindingAggregationOp.SUM})
    assert isinstance(registration.route, RouteOwnership)
    assert registration.route.resolver_id == "retencion_soportada"
    assert registration.admits_aeat_prefill is False


def test_a_clean_binding_passes_its_validator_and_registration() -> None:
    binding = _binding()
    assert registration_for(BindingSourceKind.RETENCION_SOPORTADA).validator(binding) == []
    assert validate_binding_against_registration(binding) == ()


@pytest.mark.parametrize(
    ("binding", "fragment"),
    [
        (_binding(data_type=BindingDataType.DECIMAL), "data_type must be money"),
        (_binding(data_type=BindingDataType.INTEGER, channel=BindingValueChannel.INTEGER), "channel must be decimal"),
        (_binding(op=BindingAggregationOp.COPY), "must be sum"),
    ],
)
def test_the_family_validator_refuses_each_isolated_shape_defect(binding: BindingDefinition, fragment: str) -> None:
    failures = registration_for(BindingSourceKind.RETENCION_SOPORTADA).validator(binding)
    assert any(fragment in failure for failure in failures), failures


def test_the_registration_refuses_an_operation_outside_sum() -> None:
    assert validate_binding_against_registration(_binding(op=BindingAggregationOp.COPY)) != ()


def test_a_clean_revision_earns_no_revision_failure() -> None:
    revision = _revision(binding=_binding())
    assert revision_declares_retencion_soportada(revision)
    assert credit_casilla_ids(revision) == frozenset({_TRABAJO_CASILLA, _CAPITAL_CASILLA})
    assert retencion_soportada_revision_failures(revision) == ()


def test_a_revision_without_the_family_is_not_inspected() -> None:
    revision = minimal_revision()
    assert not revision_declares_retencion_soportada(revision)
    assert retencion_soportada_revision_failures(revision) == ()


def test_a_class_bound_to_another_class_role_is_refused() -> None:
    failures = retencion_soportada_revision_failures(_revision(binding=_binding(income_class="capital_mobiliario")))
    assert any("does not credit casilla '0596'" in failure for failure in failures), failures


def test_a_credit_outside_the_payments_on_account_total_is_refused() -> None:
    failures = retencion_soportada_revision_failures(
        _revision(binding=_binding(), bound_casilla="0598", bound_role="irpf_retencion_trabajo"),
    )
    assert any("not an operand" in failure for failure in failures), failures
    assert _OUTSIDE_CASILLA not in credit_casilla_ids(
        _revision(binding=_binding(), bound_casilla="0598", bound_role="irpf_retencion_trabajo"),
    )


def test_a_revision_with_no_total_admits_no_credit() -> None:
    revision = minimal_revision(
        casillas=(_casilla("0596", "irpf_retencion_trabajo", bound=True),),
        bindings=(_binding(),),
    )
    assert credit_casilla_ids(revision) == frozenset()
    assert any("not an operand" in failure for failure in retencion_soportada_revision_failures(revision))


def test_a_binding_on_a_computed_casilla_is_refused() -> None:
    revision = _revision(binding=_binding())
    computed = tuple(
        casilla.model_copy(update={"input_kind": InputKind.COMPUTED, "formula": "test.other"})
        if casilla.id == _TRABAJO_CASILLA
        else casilla
        for casilla in revision.casillas
    )
    failures = retencion_soportada_revision_failures(revision.model_copy(update={"casillas": computed}))
    assert any("computed casilla '0596'" in failure for failure in failures), failures


@pytest.mark.parametrize("quantity", ["retencion", "importe_integro"])
def test_a_quantity_outside_the_income_table_is_refused_on_every_casilla(quantity: str) -> None:
    failures = retencion_soportada_revision_failures(_revision(binding=_binding(quantity=quantity)))
    assert any(f"quantity {quantity!r}" in failure and "no casilla role" in failure for failure in failures), failures


@pytest.mark.parametrize("quantity", ["ingreso_a_cuenta", "ingreso_a_cuenta_repercutido"])
def test_an_income_quantity_on_the_credit_casilla_is_refused_for_its_role(quantity: str) -> None:
    failures = retencion_soportada_revision_failures(_revision(binding=_binding(quantity=quantity)))
    assert any("casilla '0596' has role 'irpf_retencion_trabajo'" in failure for failure in failures), failures


_INCOME_PAIRS = {
    "importe_integro_dinerario": ("0003", "irpf_rendimiento_trabajo_importe_integro_dinerario"),
    "valoracion_especie": ("0004", "irpf_rendimiento_trabajo_especie_valoracion"),
    "ingreso_a_cuenta": ("0005", "irpf_rendimiento_trabajo_especie_ingreso_cuenta"),
    "ingreso_a_cuenta_repercutido": ("0006", "irpf_rendimiento_trabajo_especie_ingreso_cuenta_repercutido"),
    "reducciones_aplicables": ("0011", "irpf_rendimiento_trabajo_reduccion"),
    "gastos_deducibles": ("0013", "irpf_rendimiento_trabajo_gasto_ss_mutualidad"),
}


def _income_binding_id(quantity: str) -> str:
    return f"income-{quantity.replace('_', '-')}"


def _income_binding(quantity: str, *, income_class: str = "trabajo", **update: object) -> BindingDefinition:
    return _binding(income_class=income_class, quantity=quantity).model_copy(
        update={"id": _income_binding_id(quantity), **update},
    )


def _income_revision(
    *,
    bindings: dict[str, BindingDefinition] | None = None,
    casilla_updates: dict[str, dict[str, object]] | None = None,
    formulas: tuple[FormulaDefinition, ...] = (),
):
    """A clean revision: the credit set plus the six income casillas, each bound to its own family binding."""
    base = _revision(binding=_binding())
    declared = bindings or {quantity: _income_binding(quantity) for quantity in _INCOME_PAIRS}
    casillas = list(base.casillas)
    for quantity, (number, role) in _INCOME_PAIRS.items():
        update: dict[str, object] = {"input_kind": InputKind.BOUND, "binding": _income_binding_id(quantity)}
        update.update((casilla_updates or {}).get(number, {}))
        casillas.append(_casilla(number, role).model_copy(update=update))
    return base.model_copy(
        update={
            "casillas": tuple(casillas),
            "bindings": (*base.bindings, *declared.values()),
            "formulas": (*base.formulas, *formulas),
        },
    )


def test_a_clean_income_revision_earns_no_failure_and_the_table_is_the_six_trabajo_pairs() -> None:
    assert retencion_soportada_revision_failures(_income_revision()) == ()
    assert set(RETENCION_SOPORTADA_INCOME_ROLES) == {
        (RetencionSoportadaClase.TRABAJO, RetencionSoportadaCantidad(quantity)) for quantity in _INCOME_PAIRS
    }
    assert {role for _, role in _INCOME_PAIRS.values()} == set(RETENCION_SOPORTADA_INCOME_ROLES.values())


def test_a_second_source_on_an_income_casilla_is_refused() -> None:
    other = _income_binding("importe_integro_dinerario").model_copy(update={"id": "second-source"})
    revision = _income_revision(casilla_updates={"0003": {"alternate_bindings": ("second-source",)}})
    revision = revision.model_copy(update={"bindings": (*revision.bindings, other)})
    failures = retencion_soportada_revision_failures(revision)
    assert any("alternate binding of casilla '0003'" in failure for failure in failures), failures
    assert any("exactly its family binding" in failure and "'0003'" in failure for failure in failures), failures


def test_the_combined_importe_integro_bound_to_an_income_casilla_is_refused() -> None:
    declared = {quantity: _income_binding(quantity) for quantity in _INCOME_PAIRS}
    declared["importe_integro_dinerario"] = _income_binding("importe_integro_dinerario").model_copy(
        update={"provider": _binding(quantity="importe_integro").provider},
    )
    failures = retencion_soportada_revision_failures(_income_revision(bindings=declared))
    assert any("quantity 'importe_integro'" in f and "no casilla role" in f for f in failures), failures
    assert any("exactly its family binding" in f and "'0003'" in f for f in failures), failures


@pytest.mark.parametrize("income_class", [c.value for c in RetencionSoportadaClase if c.value != "trabajo"])
def test_an_income_quantity_on_another_class_is_refused(income_class: str) -> None:
    declared = {quantity: _income_binding(quantity) for quantity in _INCOME_PAIRS}
    declared["gastos_deducibles"] = _income_binding("gastos_deducibles", income_class=income_class)
    failures = retencion_soportada_revision_failures(_income_revision(bindings=declared))
    assert any(f"income class {income_class!r} is admitted on no casilla role" in f for f in failures), failures


def test_an_income_binding_on_a_casilla_of_another_role_is_refused() -> None:
    revision = _income_revision()
    casillas = tuple(
        casilla.model_copy(update={"semantic_role": "irpf_rendimiento_trabajo_reduccion"})
        if casilla.id == validated_casilla_id("0013")
        else casilla
        for casilla in revision.casillas
    )
    failures = retencion_soportada_revision_failures(revision.model_copy(update={"casillas": casillas}))
    assert any("'0013' has role 'irpf_rendimiento_trabajo_reduccion'" in f for f in failures), failures


def test_an_income_binding_read_only_as_a_formula_operand_is_refused() -> None:
    operand = FormulaDefinition(
        id="test.operand",
        target_casilla_id=validated_casilla_id("0007"),
        expression=FormulaExpression(binding=_income_binding_id("importe_integro_dinerario")),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = _income_revision(
        casilla_updates={"0003": {"input_kind": InputKind.MANUAL, "binding": None}},
        formulas=(operand,),
    )
    failures = retencion_soportada_revision_failures(revision)
    assert any("cannot be a formula operand" in failure for failure in failures), failures
    assert any("no casilla binds it" in failure for failure in failures), failures


def test_an_income_binding_with_aeat_prefilled_is_refused() -> None:
    declared = {quantity: _income_binding(quantity) for quantity in _INCOME_PAIRS}
    declared["valoracion_especie"] = _income_binding("valoracion_especie", aeat_prefilled=True)
    failures = retencion_soportada_revision_failures(_income_revision(bindings=declared))
    assert any("cannot be aeat_prefilled" in failure for failure in failures), failures


def test_declaring_one_income_binding_requires_every_income_role_to_take_its_family_binding() -> None:
    only_one = {"importe_integro_dinerario": _income_binding("importe_integro_dinerario")}
    failures = retencion_soportada_revision_failures(_income_revision(bindings=only_one))
    assert len([f for f in failures if "exactly its family binding" in f]) == 5, failures


def test_an_income_role_casilla_with_a_foreign_binding_is_refused_once_the_family_declares_income() -> None:
    revision = _income_revision(casilla_updates={"0013": {"input_kind": InputKind.MANUAL, "binding": None}})
    failures = retencion_soportada_revision_failures(revision)
    assert any("'0013'" in f and "exactly its family binding" in f for f in failures), failures


def test_a_revision_declaring_only_credits_leaves_income_role_casillas_alone() -> None:
    revision = _revision(binding=_binding())
    casillas = (*revision.casillas, _casilla("0003", "irpf_rendimiento_trabajo_importe_integro_dinerario"))
    assert retencion_soportada_revision_failures(revision.model_copy(update={"casillas": casillas})) == ()
