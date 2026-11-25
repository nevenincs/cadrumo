"""Cash-accounting ledger rows shared by the aggregation and profile-persistence suites."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_DEFAULT_TREATMENT = IvaCashAccountingTreatment("none")


def cash_accounting_raw(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente criterio caja",
        description=f"cash-accounting {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(1980, 4, 1, 10, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def cash_accounting_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    booked_date: date,
    taxable_base: Decimal,
    iva_amount: Decimal,
    cash_accounting_treatment: IvaCashAccountingTreatment = _DEFAULT_TREATMENT,
    operation_date: date | None = None,
    cash_accounting_payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...] = (),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": cash_accounting_raw(provider_id, booked_date=booked_date, amount=taxable_base + iva_amount),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "iva_category": IvaCategory("domestic_general"),
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_current")
            if direction is TransactionDirection.OUTGOING
            else None,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                source_locator=f"invoice:{provider_id}",
                evidence_digest="a" * 64,
            )
            if direction is TransactionDirection.OUTGOING
            else None,
            "cash_accounting_treatment": cash_accounting_treatment,
            "operation_date": operation_date,
            "cash_accounting_payment_evidence": cash_accounting_payment_evidence,
            "classified_at": datetime(1980, 4, 1, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
