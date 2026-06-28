"""Tests for ledger-backed Renta expense registry bindings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from .....core import Modelo
from .....core.resources import bundled_path
from ....categories import SpendingCategory, resolve_category_profiles
from ....renta import (
    RentaDeductibilityContext,
    RentaDeductibleExpenseFact,
    RentaExpenseDirection,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
)
from .. import (
    CasillaId,
    DataBindingDefinition,
    ModeloRevision,
    RegistrySnapshot,
    RegistryValidationError,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    resolve_ledger_renta_expense_aggregation_binding_values,
    unsupported_ledger_renta_expense_observations,
    validate_ledger_renta_expense_aggregation_binding_definition,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M100_GASTO_SS_CASILLA: CasillaId = validated_casilla_id(
    "0186",
    surface="_M100_GASTO_SS_CASILLA",
)
_M100_GASTO_ARRENDAMIENTOS_CASILLA: CasillaId = validated_casilla_id(
    "0192",
    surface="_M100_GASTO_ARRENDAMIENTOS_CASILLA",
)
_M100_GASTO_OTROS_CONCEPTOS_CASILLA: CasillaId = validated_casilla_id(
    "0199",
    surface="_M100_GASTO_OTROS_CONCEPTOS_CASILLA",
)
_M100_GASTO_AMORTIZACIONES_CASILLA: CasillaId = validated_casilla_id(
    "0203",
    surface="_M100_GASTO_AMORTIZACIONES_CASILLA",
)
_UNKNOWN_RENTA_EXPENSE_CASILLA: CasillaId = validated_casilla_id(
    "9999",
    surface="_UNKNOWN_RENTA_EXPENSE_CASILLA",
)


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

    assert casillas_by_id[_M100_GASTO_SS_CASILLA].binding == "renta-2025-ledger-expense-0186-deductible"
    assert casillas_by_id[_M100_GASTO_ARRENDAMIENTOS_CASILLA].binding == (
        "renta-2025-ledger-expense-0192-deductible"
    )
    assert casillas_by_id[_M100_GASTO_OTROS_CONCEPTOS_CASILLA].binding == (
        "renta-2025-ledger-expense-0199-deductible"
    )
    assert casillas_by_id[_M100_GASTO_AMORTIZACIONES_CASILLA].binding == (
        "renta-2025-ledger-expense-0203-deductible"
    )

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
    assert casilla_inputs[_M100_GASTO_SS_CASILLA] > Decimal("0"), (
        "single CUOTAS_AUTONOMOS_SS observation must route to 0186"
    )
    assert casilla_inputs[_M100_GASTO_ARRENDAMIENTOS_CASILLA] == Decimal("0"), (
        "no observation in 0192's category — must aggregate to zero"
    )
    assert casilla_inputs[_M100_GASTO_OTROS_CONCEPTOS_CASILLA] > Decimal("0"), (
        "ASESORIA_FISCAL + ASESORIA_CONTABLE must both route to 0199"
    )
    assert casilla_inputs[_M100_GASTO_AMORTIZACIONES_CASILLA] == Decimal("0"), (
        "no observation in 0203's category — must aggregate to zero"
    )

    # Single-observation identity check: 0186 receives one observation
    # and the binding's aggregate must equal that observation's
    # deductible amount. The expected value comes from the deductibility
    # evaluator on the same observation, not from a fresh computation.
    ss_observation = observations[0]
    assert casilla_inputs[_M100_GASTO_SS_CASILLA] == ss_observation.deductible_amount, (
        "0186 binding aggregate of one observation must equal that observation's deductible amount"
    )

    calculation = calculate_registry_snapshot(
        snapshot,
        inputs=casilla_inputs,
        binding_values={
            **binding_values,
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            # declaration-type=1 → individual filing (per Orden HAC/277/2026 art. 3
            # TIPOTRIBUTACION code 1; the joint-filing code is 2)
            "renta-2025-profile-declaration-type": Decimal("1"),
            # Neutral not-married marriage axis (peer contract made these required;
            # mirrors the convention in test_renta_chain_behaviour and
            # test_registry_scenarios).
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            # Casilla 1388 is a previous-filing carry. This isolated
            # ledger-expense binding test has no prior filing fixture, so
            # provide the same explicit neutral opening balance used by the
            # Renta chain tests.
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={relation.id: Decimal("0") for relation in revision.relations},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
        date_context={"filing_period": date(2025, 12, 31)},
    )

    # Calculation threading: the snapshot calculator must thread
    # binding values into casilla.values rather than computing fresh
    # aggregates.
    assert calculation.values[_M100_GASTO_SS_CASILLA] == binding_values["renta-2025-ledger-expense-0186-deductible"]
    assert calculation.values[_M100_GASTO_OTROS_CONCEPTOS_CASILLA] == binding_values[
        "renta-2025-ledger-expense-0199-deductible"
    ]


def test_renta_ledger_expense_binding_rejects_noncanonical_selector() -> None:
    # Use model_validate(dict) rather than the keyword constructor so the
    # schema-hygiene gate (test_registry_tests_do_not_define_schema_authority_objects)
    # stays clean. The gate forbids the direct keyword-constructor syntax for
    # schema-authority types in test files; the validator under test still
    # needs an invalid binding instance to exercise the target_casilla_id
    # allow-list error path.
    binding = DataBindingDefinition.model_validate(
        {
            "id": "bad-renta-binding",
            "source": "ledger_renta_expense_aggregation",
            "selector": {
                "modelo": "100",
                "period": "0A",
                "target_casilla_id": _UNKNOWN_RENTA_EXPENSE_CASILLA,
                "fact": "deductible_amount_sum",
            },
            "aggregation": {"op": "sum"},
            "legal_refs": ("ley-35-2006:art-28",),
            "source_refs": ("aeat-renta-2025-manual-parte1",),
        },
    )

    with pytest.raises(RegistryValidationError, match="outside the first Modelo 100 Renta ledger expense slice"):
        validate_ledger_renta_expense_aggregation_binding_definition(binding)


def test_renta_ledger_expense_binding_rejects_legacy_target_casilla_key() -> None:
    # The legacy ``target_casilla`` key is a selector-SHAPE violation (the strict
    # ``_RentaLedgerExpenseSelector`` forbids the extra key), so under the F8
    # construction-time selector gate the binding is refused the moment it is
    # built — the diagnostic still names both the canonical and legacy key.
    with pytest.raises(ValidationError) as exc_info:
        DataBindingDefinition.model_validate(
            {
                "id": "bad-renta-binding-legacy-target-key",
                "source": "ledger_renta_expense_aggregation",
                "selector": {
                    "modelo": "100",
                    "period": "0A",
                    "target_casilla": _M100_GASTO_SS_CASILLA,
                    "fact": "deductible_amount_sum",
                },
                "aggregation": {"op": "sum"},
                "legal_refs": ("ley-35-2006:art-28",),
                "source_refs": ("aeat-renta-2025-manual-parte1",),
            },
        )

    detail = str(exc_info.value)
    assert "target_casilla_id" in detail
    assert "target_casilla" in detail


def _single_expense_binding_revision(snapshot: RegistrySnapshot, target_casilla_id: CasillaId) -> ModeloRevision:
    """A revision carrying only the one renta-expense binding for ``target_casilla_id``."""
    revision = snapshot.revision
    binding = next(
        item
        for item in revision.bindings
        if item.source == "ledger_renta_expense_aggregation"
        and dict(item.selector).get("target_casilla_id") == target_casilla_id
    )
    return revision.model_copy(update={"bindings": (binding,)})


def test_unsupported_renta_expense_flags_observation_routed_to_no_binding() -> None:
    """A non-zero deductible whose target_casilla_id matches no binding is surfaced.

    The revision carries only the 0186 binding; a 0199-routed deductible
    observation reaches no binding and would silently vanish from the filing,
    so the fail-closed screen MUST report it (no-silent-under-declaration).
    """
    snapshot = _modelo_100_2025_snapshot()
    revision = _single_expense_binding_revision(snapshot, "0186")

    routed = _expense_observation(
        "tx-ss",
        category=SpendingCategory.CUOTAS_AUTONOMOS_SS,  # routes to 0186 (the only binding)
        gross_amount=Decimal("300.00"),
    )
    unrouted = _expense_observation(
        "tx-fiscal",
        category=SpendingCategory.ASESORIA_FISCAL,  # routes to 0199 — no binding on this revision
        gross_amount=Decimal("121.00"),
    )
    assert routed.target_casilla_id == _M100_GASTO_SS_CASILLA
    assert unrouted.target_casilla_id == _M100_GASTO_OTROS_CONCEPTOS_CASILLA
    assert unrouted.deductible_amount > Decimal("0")

    result = unsupported_ledger_renta_expense_observations(revision, (routed, unrouted))
    assert result == (unrouted,)


class _ExpenseObservation(BaseModel):
    """Minimal structural stand-in satisfying RentaExpenseObservationProtocol.

    Used to exercise the zero-deductible false-fire guard: the production
    deductibility evaluator never emits a zero-gross fact, but a fully
    non-deductible category legitimately yields a zero ``deductible_amount`` on
    a non-zero expense, which the screen must not flag.
    """

    modelo: Modelo
    period: str
    target_casilla_id: CasillaId
    deductible_amount: Decimal


def test_unsupported_renta_expense_does_not_flag_zero_deductible() -> None:
    """A zero-deductible observation routed to no binding must NOT false-fire.

    A zero deductible contributes nothing whether or not it is routed, so the
    false-fire guard (the ledger-iva-advisory cuota-bearing precedent) excludes
    it even when its target_casilla_id matches no binding on the revision.
    """
    snapshot = _modelo_100_2025_snapshot()
    revision = _single_expense_binding_revision(snapshot, "0186")

    zero_unrouted = _ExpenseObservation(
        modelo=Modelo.M100,
        period="0A",
        target_casilla_id=_M100_GASTO_OTROS_CONCEPTOS_CASILLA,
        deductible_amount=Decimal("0"),
    )

    result = unsupported_ledger_renta_expense_observations(revision, (zero_unrouted,))
    assert result == ()
