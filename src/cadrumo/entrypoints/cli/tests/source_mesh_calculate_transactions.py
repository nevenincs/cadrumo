"""Ledger transaction builders for the source mesh-backed modelo calculation CLI tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
)
from cadrumo.domain.contribuyente.inventory.records import InventoryLedger, ValuationMethod
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from cadrumo.domain.iva.schema import EUMemberState, IvaCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_YEAR = filing_year_envelope().horizon


def ledger_raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(_YEAR, 2, 10),
    amount: Decimal,
) -> RawTransaction:
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
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(_YEAR, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def ledger_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
    # Defaults to the general tipo, which every rate-bearing row in this file
    # declares. A category whose cuota is zero by law takes an explicit ZERO
    # tipo rather than an absent one: the missing-fact screen refuses a row with
    # no iva_rate at all, and the zero-cuota guard refuses any tipo that is not
    # exactly 0, so Decimal("0") is the one value satisfying both. (That the
    # other rows here rely on the default is a fact about the file today, not a
    # contract.)
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_category: IvaCategory | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
    deduction_locator: str | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
) -> Transaction:
    raw = ledger_raw_transaction(provider_id, amount=amount)
    fields: dict[str, object] = {
        "raw": raw,
        # Stated, so the period never rests on the bank date and the source-advisory
        # assertions in this file see only the advisories they are about.
        "operation_date": raw.booked_date,
        "direction": direction,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "material_oficina",
        "taxable_base": taxable_base,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "classified_at": datetime(_YEAR, 2, 11, 13, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if iva_category is not None:
        fields["iva_category"] = iva_category
    if deduction_fact_kind is not None:
        # LIVA art. 97: the factura confers the right to deduct, so an input
        # row only reaches a soportado binding once it carries its
        # invoice-evidence deduction authority.
        fields["deduction_fact_kind"] = deduction_fact_kind
        fields["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator=deduction_locator or "invoice:test-purchase",
            evidence_digest="a" * 64,
        )
    if counterparty_country is not None:
        fields["counterparty_country"] = counterparty_country
    if counterparty_identification_state is not None:
        fields["counterparty_identification_state"] = counterparty_identification_state
    return Transaction.model_validate(fields)


def classified_rent_transaction() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(
                "rent-net-withholding",
                booked_date=date(_YEAR, 3, 15),
                amount=Decimal("2754.00"),
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "category_id": "arrendamiento_local",
            "taxable_base": Decimal("2700.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("567.00"),
            "irpf_category": "arrendamiento_local",
            "classified_at": datetime(_YEAR, 3, 15, 12, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def m100_activity_income_transaction() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(
                "m100-activity-income",
                booked_date=date(_YEAR, 3, 15),
                amount=Decimal("12000.00"),
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "taxable_base": Decimal("12000.00"),
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "classified_at": datetime(_YEAR, 3, 15, 12, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def m100_activity_expense_transaction(
    transaction_id: str,
    *,
    value_date: date,
    category: SpendingCategory,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * Decimal("0.21")).quantize(Decimal("0.01"))
    gross_amount = taxable_base + iva_amount
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(
                transaction_id,
                booked_date=value_date,
                amount=gross_amount,
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "category_id": category.value,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(_YEAR, 3, 15, 12, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def zero_stock_inventory_ledger(actividad_id: str, *, year: int) -> InventoryLedger:
    """Return the complete activity book of a filer who held no existencias at either end of ``year``.

    The book has no opening stock and no movement, and its closing decision carries the
    prior year's zero close as continuity evidence, so the Anexo D rows resolve to zero.
    """
    continuity = (
        PriorClosingContinuityEvidence(
            reference=FilingEvidenceReference(reference=f"prior-{actividad_id}"), content_digest="f" * 64
        ),
    )
    prior_fingerprint = fingerprint_prior_authoritative_closing(
        actividad_id=actividad_id,
        filing_year=year - 1,
        authoritative_closing_value=Decimal("0.00"),
        authoritative_source_fingerprint="e" * 64,
        evidence=continuity,
    )
    return InventoryLedger.model_validate(
        {
            "actividad_id": actividad_id,
            "year": year,
            "valuation_method": ValuationMethod.FIFO,
            "opening_stock": Decimal("0.00"),
            "period_movements": (),
            "closing_authority_record": {
                "decision": {
                    "decision_id": f"decision-{actividad_id}",
                    "actividad_id": actividad_id,
                    "filing_year": year,
                    "authority": InventoryClosingAuthority.MOVEMENT_DERIVED,
                    "physical_observation_id": None,
                    "physical_observation_fingerprint": None,
                    "reason": "No existencias held.",
                    "actor": "manual",
                    "source_command": "synthetic-test-seed",
                    "decided_at": datetime(year + 1, 1, 2, tzinfo=UTC),
                    "evidence": (
                        InventoryClosingDecisionEvidence(
                            reference=FilingEvidenceReference(reference=f"decision-{actividad_id}"),
                            role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                            content_digest="d" * 64,
                        ),
                    ),
                },
                "physical_observation": None,
                "prior_closing_link": {
                    "actividad_id": actividad_id,
                    "current_filing_year": year,
                    "prior_filing_year": year - 1,
                    "prior_authoritative_closing_value": Decimal("0.00"),
                    "current_opening_value": Decimal("0.00"),
                    "prior_authoritative_source_fingerprint": "e" * 64,
                    "prior_authoritative_closing_fingerprint": prior_fingerprint,
                    "evidence": continuity,
                },
            },
        },
    )
