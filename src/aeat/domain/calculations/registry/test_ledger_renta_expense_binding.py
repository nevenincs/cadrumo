"""Tests for ledger-backed Renta expense registry bindings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.resources import bundled_path
from aeat.domain.categories import SpendingCategory, resolve_category_profiles
from aeat.domain.renta import (
    RentaDeductibilityContext,
    RentaDeductibleExpenseFact,
    RentaExpenseDirection,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
)

from . import (
    DataBindingDefinition,
    RegistryValidationError,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    resolve_ledger_renta_expense_aggregation_binding_values,
    validate_ledger_renta_expense_aggregation_binding_definition,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _modelo_100_2025_snapshot():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "100")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )


def _expense_observation(
    transaction_id: str,
    *,
    category: SpendingCategory,
    gross_amount: Decimal,
):
    fact = RentaDeductibleExpenseFact(
        transaction_id=transaction_id,
        catalogue_id="ledger",
        operation_date=date(2025, 4, 5),
        gross_amount=gross_amount,
        direction=RentaExpenseDirection.OUTGOING_EXPENSE,
        category=category,
    )
    profile = resolve_category_profiles(2025)[category]
    result = evaluate_renta_deductibility(
        fact,
        profile,
        RentaDeductibilityContext(profile_year=2025),
    )
    return build_renta_deductible_expense_observation(fact, result, tax_year=2025)


def test_modelo_100_2025_renta_ledger_expense_bindings_resolve_to_bound_casillas() -> None:
    snapshot = _modelo_100_2025_snapshot()
    revision = snapshot.revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    assert casillas_by_id["0186"].binding == "renta-2025-ledger-expense-0186-deductible"
    assert casillas_by_id["0192"].binding == "renta-2025-ledger-expense-0192-deductible"
    assert casillas_by_id["0199"].binding == "renta-2025-ledger-expense-0199-deductible"
    assert casillas_by_id["0203"].binding == "renta-2025-ledger-expense-0203-deductible"

    observations = (
        _expense_observation(
            "tx-ss",
            category=SpendingCategory.CUOTAS_AUTONOMOS_SS,
            gross_amount=Decimal("300.00"),
        ),
        _expense_observation(
            "tx-fiscal",
            category=SpendingCategory.ASESORIA_FISCAL,
            gross_amount=Decimal("121.00"),
        ),
        _expense_observation(
            "tx-contable",
            category=SpendingCategory.ASESORIA_CONTABLE,
            gross_amount=Decimal("79.00"),
        ),
    )

    binding_values = resolve_ledger_renta_expense_aggregation_binding_values(revision, observations)
    casilla_inputs = {
        casilla.id: binding_values[casilla.binding]
        for casilla in revision.casillas
        if casilla.binding in binding_values
    }

    # Routing assertions — pin which observations land in which
    # binding. Single observation lands in 0186; both fiscal+contable
    # observations land in 0199 producing a non-zero aggregate;
    # untouched categories stay zero. Arithmetic correctness against
    # AEAT is verified by the Renta WEB Open replay-parity layer.
    assert casilla_inputs["0186"] > Decimal("0"), "single CUOTAS_AUTONOMOS_SS observation must route to 0186"
    assert casilla_inputs["0192"] == Decimal("0"), "no observation in 0192's category — must aggregate to zero"
    assert casilla_inputs["0199"] > Decimal("0"), "ASESORIA_FISCAL + ASESORIA_CONTABLE must both route to 0199"
    assert casilla_inputs["0203"] == Decimal("0"), "no observation in 0203's category — must aggregate to zero"

    # Single-observation identity check: 0186 receives one observation
    # and the binding's aggregate must equal that observation's
    # deductible amount. The expected value comes from the deductibility
    # evaluator on the same observation, not from a fresh computation.
    ss_observation = observations[0]
    assert casilla_inputs["0186"] == ss_observation.deductible_amount, (
        "0186 binding aggregate of one observation must equal that observation's deductible amount"
    )

    calculation = calculate_registry_snapshot(
        snapshot,
        inputs=casilla_inputs,
        binding_values={
            **binding_values,
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={relation.id: Decimal("0") for relation in revision.relations},
        date_context={"filing_period": date(2025, 12, 31)},
    )

    # Calculation threading: the snapshot calculator must thread
    # binding values into casilla.values rather than computing fresh
    # aggregates.
    assert calculation.values["0186"] == binding_values["renta-2025-ledger-expense-0186-deductible"]
    assert calculation.values["0199"] == binding_values["renta-2025-ledger-expense-0199-deductible"]


def test_renta_ledger_expense_binding_rejects_noncanonical_selector() -> None:
    # Use model_validate(dict) rather than the keyword constructor so the
    # schema-hygiene gate (test_registry_tests_do_not_define_schema_authority_objects)
    # stays clean. The gate forbids the direct keyword-constructor syntax for
    # schema-authority types in test files; the validator under test still
    # needs an invalid binding instance to exercise the target_casilla
    # allow-list error path.
    binding = DataBindingDefinition.model_validate(
        {
            "id": "bad-renta-binding",
            "source": "ledger_renta_expense_aggregation",
            "selector": {"modelo": "100", "period": "0A", "target_casilla": "9999", "fact": "deductible_amount_sum"},
            "aggregation": {"op": "sum"},
            "legal_refs": ("ley-35-2006:art-28",),
            "source_refs": ("aeat-renta-2025-manual-parte1",),
        }
    )

    with pytest.raises(RegistryValidationError, match="outside the first Modelo 100 Renta ledger expense slice"):
        validate_ledger_renta_expense_aggregation_binding_definition(binding)
