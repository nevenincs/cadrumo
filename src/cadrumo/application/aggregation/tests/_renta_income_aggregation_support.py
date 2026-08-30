from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_ANNUAL_2024 = _period(2024, "0A")
_Q1_2024 = _period(2024, "1T")
_Q2_2024 = _period(2024, "2T")


_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA: CasillaId = validated_casilla_id("0171")
_M130_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    value_date: date | None,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Cliente SA",
        description=f"income row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _income_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _actividad_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal = Decimal("1000.00"),
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    irpf_category: str | None = "actividad_economica",
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    business_pct: Decimal | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _actividad_transaction_with_source(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal,
    source_jurisdiction: str | None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "source_jurisdiction": source_jurisdiction,
        },
    )
