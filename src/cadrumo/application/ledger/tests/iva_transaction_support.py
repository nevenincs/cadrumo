"""Classified 21% IVA business transactions for ledger application tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_IVA_RATE = Decimal("0.21")
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)


def _raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        description=f"IVA transaction {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=date(2026, 2, 15),
                amount=taxable_base + iva_amount,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "material_oficina",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            "deduction_fact_kind": (
                IvaDeductionFactKind.from_registry("domestic_current")
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )
