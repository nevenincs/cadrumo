"""M130 actividad income contract tests for IRPF category and taxable-base projection."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.resources import resources
from ....domain.calculations.registry import resolve_ledger_renta_income_aggregation_binding_values
from ....domain.transactions import BusinessClassification, TransactionCatalogue, TransactionCatalogueRepository
from .._modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from .._renta_income_ledger import RentaIncomeLedgerAggregationIssueReason, aggregate_renta_income_ledger
from .._source_mesh import CalculationSourceContext
from ._renta_income_aggregation_support import (
    _M130_INGRESOS_CASILLA,
    _M130_RETENCIONES_BINDING,
    _M130_RETENCIONES_CASILLA,
    _Q1_2024,
    _actividad_transaction,
    _period,
    isolated_renta_income_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_renta_income_objects(tmp_path) as objects:
        yield objects


# contract: irpf_category filter + taxable_base_sum fact
# Grounded in RD 439/2007 art. 110.2 — only actividades económicas feed M130.
# ---------------------------------------------------------------------------


def test_irpf_actividad_economica_flows_despite_unclassified_business() -> None:
    """irpf_category='actividad_economica' is the M130 eligibility gate.

    RD 439/2007 art. 110.2: pagos fraccionados apply to rendimientos de
    actividades económicas.  A transaction explicitly tagged as
    irpf_category='actividad_economica' must flow to casilla 01 even when
    business_classification has not yet been resolved (UNCLASSIFIED).

    This is the root-cause regression: Andrea's transactions had
    irpf_category set but business_classification=UNCLASSIFIED, causing
    _income_business_amount to return None and casilla 01 to be 0.
    """
    # Amount matches the AEAT professional-services income example: a single
    # quarterly invoice of 3000 EUR from estimación directa simplified.
    amount = Decimal("3000.00")
    tx = _actividad_transaction(
        "ae-001",
        value_date=date(2024, 2, 1),
        amount=amount,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert len(result.observations) == 1, result
    assert result.observations[0].gross_amount == amount
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == amount
    assert result.issues == ()


def test_trabajo_income_excluded_from_m130() -> None:
    """irpf_category='trabajo' transactions are excluded from M130 casillas.

    Rendimientos del trabajo (nóminas) are never subject to M130 pagos
    fraccionados — only actividades económicas trigger M130 (RD 439/2007
    art. 110.1). The pipeline must reject trabajo entries with TRABAJO_INCOME
    reason so they do not inflate casilla 01.
    """
    nomina = _actividad_transaction(
        "nomina-001",
        value_date=date(2024, 1, 31),
        amount=Decimal("2500.00"),
        irpf_category="trabajo",
        business_classification=BusinessClassification.BUSINESS,
    )
    actividad = _actividad_transaction(
        "ae-002",
        value_date=date(2024, 1, 15),
        amount=Decimal("1800.00"),
    )
    catalogue = TransactionCatalogue.from_transactions((nomina, actividad))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert len(result.observations) == 1
    assert result.observations[0].transaction_id == actividad.transaction_id
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.TRABAJO_INCOME
    assert result.issues[0].transaction_id == nomina.transaction_id
    # casilla 01 only reflects the actividad transaction
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == Decimal("1800.00")


def test_taxable_base_amount_populated_when_set() -> None:
    """RentaIncomeObservation carries taxable_base_amount when transaction has taxable_base.

    The taxable_base_sum fact path lets the registry resolver sum the
    IVA-exclusive base imponible rather than gross_amount.  When a transaction
    carries taxable_base, the observation's taxable_base_amount must equal it.
    """
    # Professional invoice: 1000 EUR net + 210 EUR IVA = 1210 EUR gross.
    # The IRPF base (taxable_base) is the IVA-exclusive 1000 EUR.
    gross = Decimal("1210.00")
    taxable = Decimal("1000.00")
    tx = _actividad_transaction(
        "ae-inv-001",
        value_date=date(2024, 3, 15),
        amount=gross,
        taxable_base=taxable,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert len(result.observations) == 1
    obs = result.observations[0]
    assert obs.gross_amount == gross
    assert obs.taxable_base_amount == taxable


def test_net_paid_professional_invoice_derives_withheld_amount_for_m130() -> None:
    """Professional invoice withholding is the invoice gross minus bank cash.

    Fixture: 2000 base + 420 IVA - 300 IRPF withholding = 2120 bank receipt.
    Modelo 130 casilla 06 is the cumulative withholding amount, while casilla
    01 remains the IVA-exclusive income base. These two expectations come from
    the invoice arithmetic and the AEAT casilla roles, not from the resolver
    implementation.
    """
    tx = _actividad_transaction(
        "ae-net-paid",
        value_date=date(2024, 3, 15),
        amount=Decimal("2120.00"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    aggregation = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)
    assert len(aggregation.observations) == 1
    observation = aggregation.observations[0]
    assert observation.taxable_base_amount == Decimal("2000.00")
    assert observation.withheld_amount == Decimal("300.00")

    revision = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T").revision
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    assert aggregation.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == Decimal("2000.00")
    assert resolved[_M130_RETENCIONES_BINDING] == Decimal("300.00")


def test_income_source_resolver_projects_withheld_amount_to_m130_casilla_06(
    secure_objects: SecureObjectRepository,
) -> None:
    tx = _actividad_transaction(
        "ae-net-paid-resolver",
        value_date=date(2026, 3, 15),
        amount=Decimal("2120.00"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
    )
    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((tx,)))
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    context = CalculationSourceContext(
        bucket_id="test",
        modelo="130",
        filing_year=2026,
        period=_period(2026, "1T"),
        revision=snapshot.revision,
    )

    resolution = LedgerRentaIncomeAggregationSourceResolver(transaction_repository=tx_repo).resolve(context)

    assert resolution.binding_values[_M130_RETENCIONES_BINDING] == Decimal("300.00")
    assert resolution.bound_inputs_by_casilla_id[_M130_RETENCIONES_CASILLA] == Decimal("300.00")


def test_casilla_projection_uses_base_for_tagged_and_gross_for_untagged() -> None:
    """Casilla 01 projection carries computable income, never IVA-inclusive gross.

    Testimonial repro shape: a tagged professional invoice (1000 base +
    210 IVA = 1210 gross) plus an untagged 500 receipt. Casilla 01 must
    project 1500 (base + gross fallback) — not 1710 (gross sum, an IVA
    over-declaration) and not 1000 (base-only, dropping the untagged
    receipt). Mirrors the registry's ``ingresos_integros_sum`` fact so the
    projection and the binding resolver cannot drift.
    """
    tagged = _actividad_transaction(
        "ae-tagged",
        value_date=date(2024, 2, 10),
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
    )
    untagged = _actividad_transaction(
        "ae-untagged",
        value_date=date(2024, 3, 5),
        amount=Decimal("500.00"),
        taxable_base=None,
    )
    catalogue = TransactionCatalogue.from_transactions((tagged, untagged))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    # Field-selection wiring contract: tagged row contributes its declared
    # IVA-exclusive base, untagged row its gross transfer amount. The
    # inequality guard proves the selection is live (a gross-summing
    # regression would produce the IVA-inflated total instead).
    projected = result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA]
    assert tagged.taxable_base is not None
    assert projected == tagged.taxable_base + untagged.raw.amount
    assert projected != tagged.raw.amount + untagged.raw.amount


def test_anti_tautology_irpf_category_controls_flow() -> None:
    """Anti-tautology: changing irpf_category changes which transactions flow.

    If the irpf_category filter were ignored, both test scenarios would
    produce the same casilla 01 total.  The inequality below fails if the
    filter has no effect.
    """
    amount = Decimal("5000.00")

    # Scenario A: one actividad + one trabajo — only actividad should flow
    actividad = _actividad_transaction(
        "ae-a",
        value_date=date(2024, 2, 15),
        amount=amount,
        irpf_category="actividad_economica",
    )
    trabajo = _actividad_transaction(
        "trab-a",
        value_date=date(2024, 2, 15),
        amount=amount,
        irpf_category="trabajo",
        business_classification=BusinessClassification.BUSINESS,
    )
    catalogue_a = TransactionCatalogue.from_transactions((actividad, trabajo))
    result_a = aggregate_renta_income_ledger(catalogue_a, bucket_id="test", period=_Q1_2024)

    # Scenario B: both transactions as actividad — both should flow
    actividad_b1 = _actividad_transaction(
        "ae-b1",
        value_date=date(2024, 2, 15),
        amount=amount,
        irpf_category="actividad_economica",
    )
    actividad_b2 = _actividad_transaction(
        "ae-b2",
        value_date=date(2024, 2, 15),
        amount=amount,
        irpf_category="actividad_economica",
    )
    catalogue_b = TransactionCatalogue.from_transactions((actividad_b1, actividad_b2))
    result_b = aggregate_renta_income_ledger(catalogue_b, bucket_id="test", period=_Q1_2024)

    casilla_a = result_a.casilla_aggregation.casilla_values.get(_M130_INGRESOS_CASILLA, Decimal("0"))
    casilla_b = result_b.casilla_aggregation.casilla_values.get(_M130_INGRESOS_CASILLA, Decimal("0"))

    assert casilla_a != casilla_b, (
        f"Anti-tautology failure: both scenarios produced casilla_01={casilla_a}; irpf_category filter has no effect"
    )
    # Scenario A: only actividad flows
    assert casilla_a == amount
    # Scenario B: both flow
    assert casilla_b == amount * 2


# ---------------------------------------------------------------------------
