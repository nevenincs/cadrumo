"""Renta expense ledger scaffolding shared by the aggregation and profile suites."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ....core.aggregation import BindingAggregation, BindingAggregationOp
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.categories.spending_category import SpendingCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_YEAR = newest_authored_edition("100")

_DEFAULT_SPENDING_CATEGORY = SpendingCategory.from_registry("asesoria_fiscal")


def m100_renta_expense_binding(binding_id: str, casilla_id: str) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider={
            "kind": "ledger_renta_gastos_estimacion_directa_aggregation",
            **{
                "modelo": "100",
                "period": "0A",
                "target_casilla_id": casilla_id,
                "fact": "deductible_amount_sum",
            },
        },
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=("ley-35-2006:art-28", "ley-35-2006:art-30"),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )


def m100_2025_renta_expense_revision() -> ModeloRevision:
    return ModeloRevision(
        id=str(_YEAR),
        localization_key=f"test.schema.revision.{_YEAR}.label",
        valid_from=date(_YEAR, 12, 31) + timedelta(days=1),
        period_selector=PeriodSelector(years=(_YEAR,), periods=("0A",)),
        legal_refs=("ley-35-2006:art-28", "ley-35-2006:art-30"),
        source_refs=("aeat-renta-2025-manual-parte1",),
        bindings=(
            m100_renta_expense_binding("renta-ledger-expense-0186-deductible", "0186"),
            m100_renta_expense_binding("renta-ledger-expense-0192-deductible", "0192"),
            m100_renta_expense_binding("renta-ledger-expense-0199-deductible", "0199"),
            m100_renta_expense_binding("renta-ledger-expense-0203-deductible", "0203"),
        ),
    )


def ledger_expense_raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(_YEAR, 4, 5),
    value_date: date | None = date(_YEAR, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Proveedor SL",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(1980, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def ledger_expense_transaction(
    provider_id: str,
    *,
    amount: Decimal = Decimal("121.00"),
    category: SpendingCategory = _DEFAULT_SPENDING_CATEGORY,
    purchase_invoice_evidence_id: str | None = None,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    booked_date: date = date(_YEAR, 4, 5),
    value_date: date | None = date(_YEAR, 4, 5),
    currency: str = "EUR",
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    irpf_category: str | None = None,
    recargo_amount: Decimal | None = None,
    usage_ratio_id: str | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": ledger_expense_raw_transaction(
                provider_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "usage_ratio_id": usage_ratio_id,
            "purchase_invoice_evidence_id": purchase_invoice_evidence_id,
            "category_id": category.value,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "recargo_amount": recargo_amount,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(1980, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
