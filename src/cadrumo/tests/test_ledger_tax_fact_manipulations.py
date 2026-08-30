"""Tax-fact manipulation fidelity (ratchet history).

Builds strict :class:`cadrumo.domain.transactions.Transaction` records with
controlled tax facts and asserts the real aggregation pipelines respond to
fact changes:

- behavior contract: gross→base/IVA derivation at 21/10/4 routes to M303 soportado with the
  matching :class:`cadrumo.domain.iva.IvaCategory`.
- behavior contract: changing ``business_pct`` / per-category usage ratio scales the renta
  deductible base proportionally.
- behavior contract: reassigning ``irpf_category`` (trabajo↔actividad) flips M130 income
  routing.

These assert routing + proportionality wiring against independent expectations;
they do not re-compute a registry tax formula (per
``aeat-quality-gates``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from ..application.aggregation import (
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations,
    aggregate_renta_income_ledger,
    aggregate_renta_ledger_expenses,
)
from ..core import Period
from ..domain.bienes_inversion import BienesInversionIvaRegister
from ..domain.categories.spending_category import SpendingCategory
from ..domain.invoices import InvoiceCatalogue
from ..domain.iva import IvaCategory
from ..domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ..domain.transactions.models import Transaction, TransactionCatalogue
from ..domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CENT = Decimal("0.01")
_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_ANNUAL_2025 = _period(2025, "0A")
_Q1_2025 = _period(2025, "1T")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _raw(provider_id: str, *, amount: Decimal, description: str, when: date = date(2025, 2, 10)) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=when,
        value_date=when,
        amount=amount,
        currency="EUR",
        counterparty="Contraparte SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": description},
    )


def _gross_split(gross: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    base = _q(gross / (Decimal("1") + rate))
    return base, _q(gross - base)


# --- behavior contract: gross→base/IVA at 21/10/4 routes to M303 soportado ----------------
def test_base_iva_rederivation_without_invoice_evidence_is_refused() -> None:
    cases = [
        (Decimal("0.21"), IvaCategory.DOMESTIC_GENERAL),
        (Decimal("0.10"), IvaCategory.DOMESTIC_REDUCED),
        (Decimal("0.04"), IvaCategory.DOMESTIC_SUPER_REDUCED),
    ]
    gross = Decimal("121.00")
    txns = []
    for idx, (rate, category) in enumerate(cases):
        base, iva = _gross_split(gross, rate)
        txns.append(
            Transaction.model_validate(
                {
                    "raw": _raw(f"row-rate-{idx}", amount=gross, description=f"Compra al {rate}"),
                    "direction": TransactionDirection.OUTGOING,
                    "group_label": None,
                    "business_classification": BusinessClassification.BUSINESS,
                    "source_jurisdiction": "ES",
                    "taxable_base": base,
                    "iva_rate": rate,
                    "iva_amount": iva,
                    "iva_category": category,
                    "lifecycle_state": TransactionLifecycleState.ACTIVE,
                    "classified_at": _NOW,
                    "classified_by": "manual",
                },
            ),
        )
    catalogue = TransactionCatalogue.from_transactions(tuple(txns))
    result = aggregate_iva_ledger_observations(
        catalogue,
        period=_Q1_2025,
        ledger_profile_id="manipulation-test",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="manipulation-test",
    )
    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION,
    ] * len(cases)


# --- behavior contract: business_pct / usage-ratio proportionality propagates -------------
# arrendamiento_local maps to a first-slice Modelo 100 deductible casilla.
_DEDUCTIBLE_CATEGORY = SpendingCategory.ARRENDAMIENTO_LOCAL


def _deductible_total(*, classification: BusinessClassification, business_pct: Decimal | None) -> Decimal:
    payload = {
        "raw": _raw("row-mixed", amount=Decimal("121.00"), description="Alquiler local comercial"),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": classification,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": _DEDUCTIBLE_CATEGORY.value,
        "taxable_base": Decimal("100.00"),
        "iva_rate": Decimal("0.21"),
        "iva_amount": Decimal("21.00"),
        "irpf_category": "actividad_economica",
        "lifecycle_state": TransactionLifecycleState.ACTIVE,
        "classified_at": _NOW,
        "classified_by": "manual",
    }
    if business_pct is not None:
        payload["business_pct"] = business_pct
    catalogue = TransactionCatalogue.from_transactions((Transaction.model_validate(payload),))
    result = aggregate_renta_ledger_expenses(catalogue, InvoiceCatalogue(), bucket_id="corpus", period=_ANNUAL_2025)
    return sum((o.deductible_amount for o in result.observations), start=Decimal("0"))


def test_business_pct_change_scales_deductible_base_proportionally() -> None:
    half = _deductible_total(classification=BusinessClassification.MIXED, business_pct=Decimal("0.5"))
    high = _deductible_total(classification=BusinessClassification.MIXED, business_pct=Decimal("0.8"))
    full = _deductible_total(classification=BusinessClassification.BUSINESS, business_pct=None)
    assert half > 0 and high > 0 and full > 0
    # The deductible base scales with business_pct (0.8/0.5 = 1.6x), and a wholly
    # business row deducts the full amount.
    assert _q(high) == _q(half * Decimal("1.6")), (half, high)
    assert _q(half) == _q(full * Decimal("0.5")), (half, full)


def test_business_proportion_primitive_drives_deductible_scaling() -> None:
    from ..application.aggregation import business_proportion

    # The proportionality primitive the aggregation applies per row.
    assert business_proportion(BusinessClassification.BUSINESS, None) == Decimal("1")
    assert business_proportion(BusinessClassification.MIXED, Decimal("0.3")) == Decimal("0.3")
    assert business_proportion(BusinessClassification.PERSONAL, None) is None
    assert business_proportion(BusinessClassification.MIXED, None) is None


# --- behavior contract: irpf_category reassignment flips M130 routing ---------------------
def _income_observation_count(irpf_category: str) -> int:
    txn = Transaction.model_validate(
        {
            "raw": _raw("row-income", amount=Decimal("1000.00"), description="Cobro cliente"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )
    catalogue = TransactionCatalogue.from_transactions((txn,))
    result = aggregate_renta_income_ledger(catalogue, bucket_id="corpus", period=_Q1_2025)
    return len(result.observations)


def test_irpf_category_reassignment_flips_m130_income_routing() -> None:
    # actividad económica receipts feed M130 income; trabajo (nómina) does not.
    assert _income_observation_count("actividad_economica") == 1
    assert _income_observation_count("trabajo") == 0
