"""Tests for the validation contract shared by the ledger aggregation binding families.

Every ledger resolver folds the rows its selector matches into one sum and reads
no other operator, so each family's validator must admit ``sum`` (declared or
defaulted) and refuse every other operator rather than validate a declaration the
resolver would silently compute as a sum.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest
from pydantic import BaseModel

from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .....core.casilla_id import validated_casilla_id
from ..errors import RegistryValidationError
from ..irnr_ledger_bindings import (
    LedgerIrnrIncomeProvider,
    validate_ledger_irnr_income_aggregation_binding,
    validate_ledger_irnr_income_aggregation_binding_definition,
)
from ..ledger_binding_validation import (
    ledger_binding_build_diagnostics,
    ledger_binding_selector,
    require_ledger_aggregation_op,
    require_ledger_fact,
    require_ledger_target_casilla,
)
from ..ledger_impatriado_bindings import validate_ledger_impatriado_income_aggregation_binding_definition
from ..ledger_renta_gastos_estimacion_directa_bindings import (
    validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition,
)
from ..ledger_renta_gastos_pago_fraccionado_bindings import (
    validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition,
)
from ..ledger_renta_income_bindings import validate_ledger_renta_income_aggregation_binding_definition
from ..schema import BindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IRNR_SELECTOR: Mapping[str, object] = {
    "kind": "ledger_irnr_income_aggregation",
    "modelo": "210",
    "target_casilla_id": "rendimientos_integros",
    "fact": "gross_income_sum",
    "source_jurisdictions": ("ES",),
}

_FAMILY_CASES: tuple[tuple[Mapping[str, object], Callable[[BindingDefinition], None]], ...] = (
    (_IRNR_SELECTOR, validate_ledger_irnr_income_aggregation_binding_definition),
    (
        {
            "kind": "ledger_impatriado_income_aggregation",
            "modelo": "151",
            "target_casilla_id": "impatriado.base-liquidable-general",
            "fact": "ingresos_integros_sum",
        },
        validate_ledger_impatriado_income_aggregation_binding_definition,
    ),
    (
        {
            "kind": "ledger_renta_income_aggregation",
            "modelo": "130",
            "target_casilla_id": "01",
            "fact": "cash_received_sum",
        },
        validate_ledger_renta_income_aggregation_binding_definition,
    ),
    (
        {"kind": "ledger_renta_gastos_estimacion_directa_aggregation", "modelo": "100", "target_casilla_id": "0183"},
        validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition,
    ),
    (
        {"kind": "ledger_renta_gastos_pago_fraccionado_aggregation", "modelo": "130", "target_casilla_id": "02"},
        validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition,
    ),
)
_FAMILY_IDS = tuple(str(selector["kind"]) for selector, _ in _FAMILY_CASES)

_NON_SUM_OPS = tuple(op for op in BindingAggregationOp if op is not BindingAggregationOp.SUM)


def _binding(selector: Mapping[str, object], op: BindingAggregationOp | None) -> BindingDefinition:
    return BindingDefinition.model_validate(
        {
            "id": "ledger-validation-probe",
            "provider": dict(selector),
            "value": {"data_type": "money", "channel": "decimal"},
            "aggregation": None if op is None else BindingAggregation(op=op),
            "legal_refs": ("rd-439-2007:art-110",),
            "source_refs": ("aeat-modelo-130-instructions",),
        },
    )


@pytest.mark.parametrize(("selector", "validate"), _FAMILY_CASES, ids=_FAMILY_IDS)
@pytest.mark.parametrize("op", [BindingAggregationOp.SUM, None], ids=["declared-sum", "defaulted-sum"])
def test_every_ledger_family_admits_a_sum_declaration(
    selector: Mapping[str, object],
    validate: Callable[[BindingDefinition], None],
    op: BindingAggregationOp | None,
) -> None:
    validate(_binding(selector, op))


@pytest.mark.parametrize(("selector", "validate"), _FAMILY_CASES, ids=_FAMILY_IDS)
@pytest.mark.parametrize("op", _NON_SUM_OPS, ids=[op.value for op in _NON_SUM_OPS])
def test_every_ledger_family_refuses_an_operator_its_resolver_cannot_evaluate(
    selector: Mapping[str, object],
    validate: Callable[[BindingDefinition], None],
    op: BindingAggregationOp,
) -> None:
    binding = _binding(selector, op)

    with pytest.raises(RegistryValidationError, match=rf"supports only aggregation op 'sum', got '{op.value}'"):
        validate(binding)


def test_build_diagnostics_report_a_refused_operator_against_its_binding() -> None:
    diagnostics = validate_ledger_irnr_income_aggregation_binding(_binding(_IRNR_SELECTOR, BindingAggregationOp.COPY))

    assert len(diagnostics) == 1
    assert "'ledger-validation-probe'" in diagnostics[0]
    assert "ledger_irnr_income_aggregation invariants violated" in diagnostics[0]
    assert "got 'copy'" in diagnostics[0]


def test_build_diagnostics_report_a_malformed_selector_before_any_invariant() -> None:
    class _NarrowerSelector(BaseModel):
        model_config = {"extra": "forbid"}

        kind: str
        modelo: str

    binding = _binding(_IRNR_SELECTOR, BindingAggregationOp.COPY)

    diagnostics = ledger_binding_build_diagnostics(
        binding,
        _NarrowerSelector,
        validate_ledger_irnr_income_aggregation_binding_definition,
    )

    assert len(diagnostics) == 1
    assert "selector violates _NarrowerSelector" in diagnostics[0]
    assert "invariants violated" not in diagnostics[0]


def test_selector_refuses_a_binding_of_another_source_kind() -> None:
    binding = _binding(_IRNR_SELECTOR, BindingAggregationOp.SUM)

    with pytest.raises(RegistryValidationError, match="is not a ledger_oss_aggregation source"):
        ledger_binding_selector(binding, BindingSourceKind.LEDGER_OSS_AGGREGATION, LedgerIrnrIncomeProvider)

    selector = ledger_binding_selector(
        binding, BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION, LedgerIrnrIncomeProvider
    )
    assert selector.target_casilla_id == "rendimientos_integros"


def test_target_casilla_outside_the_family_scope_is_refused_naming_the_scope() -> None:
    binding = _binding(_IRNR_SELECTOR, BindingAggregationOp.SUM)
    supported = frozenset({validated_casilla_id("rendimientos_integros", surface="test")})

    require_ledger_target_casilla(
        binding,
        validated_casilla_id("rendimientos_integros", surface="test"),
        supported,
        scope="probe casillas",
    )
    with pytest.raises(RegistryValidationError, match=r"is outside the probe casillas \['rendimientos_integros'\]"):
        require_ledger_target_casilla(
            binding,
            validated_casilla_id("cuota_diferencial", surface="test"),
            supported,
            scope="probe casillas",
        )


def test_fact_outside_the_family_vocabulary_is_refused() -> None:
    binding = _binding(_IRNR_SELECTOR, BindingAggregationOp.SUM)

    require_ledger_fact(binding, "gross_income_sum", frozenset({"gross_income_sum"}))
    with pytest.raises(RegistryValidationError, match="supports only facts \\['gross_income_sum'\\], got 'net_sum'"):
        require_ledger_fact(binding, "net_sum", frozenset({"gross_income_sum"}))


def test_aggregation_gate_admits_sum_and_refuses_copy_directly() -> None:
    require_ledger_aggregation_op(_binding(_IRNR_SELECTOR, None))
    with pytest.raises(RegistryValidationError, match="got 'copy'"):
        require_ledger_aggregation_op(_binding(_IRNR_SELECTOR, BindingAggregationOp.COPY))
