"""Synthetic classified ledger transactions shared by aggregation and frontend tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


def ledger_raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    """Return one manual EUR ledger row with deterministic synthetic provenance."""
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
    booked_date: date = date(2026, 2, 10),
    iva_category: IvaCategory | None = None,
    counterparty_country: str | None = None,
) -> Transaction:
    """Return one business transaction classified at 21% IVA; outgoing rows carry invoice-backed deduction."""
    fields: dict[str, object] = {
        "raw": ledger_raw_transaction(provider_id, booked_date=booked_date, amount=amount),
        "direction": direction,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "material_oficina",
        "taxable_base": taxable_base,
        "iva_rate": Decimal("0.21"),
        "iva_amount": iva_amount,
        "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if iva_category is not None:
        fields["iva_category"] = iva_category
    if counterparty_country is not None:
        fields["counterparty_country"] = counterparty_country
    if direction is TransactionDirection.OUTGOING:
        fields["deduction_fact_kind"] = IvaDeductionFactKind.from_registry("domestic_current")
        fields["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator=f"invoice:{provider_id}",
            evidence_digest="a" * 64,
        )
    return Transaction.model_validate(fields)


__all__ = ["iva_transaction", "ledger_raw_transaction"]
