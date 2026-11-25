"""Inventory books for tests that need an activity's existencias stated."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ....domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    PriorClosingContinuityEvidence,
)
from ....domain.contribuyente.inventory.closing_value_facts import (
    InventoryClosingValueFacts,
    build_closing_authority_record,
)
from ....domain.contribuyente.inventory.records import InventoryLedger, InventoryLedgerDocument, ValuationMethod
from ....domain.filing_evidence import FilingEvidenceReference


def fresh_inventory_ledger(year: int) -> InventoryLedger:
    """A book as ``inventory create`` writes it: no opening stock, no movement, no closing value yet."""
    return InventoryLedger(
        actividad_id="service-activity",
        year=year,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("0.00"),
        closing_authority_record=None,
    )


def closed_no_stock_ledger(year: int) -> InventoryLedger:
    """A book opened with no stock and closed on its movements, on the taxpayer's statement that none was held."""
    fresh = fresh_inventory_ledger(year)
    statement = FilingEvidenceReference(reference="no-stock-statement")
    record = build_closing_authority_record(
        InventoryClosingValueFacts(
            decision_id="no-stock",
            actividad_id=fresh.actividad_id,
            year=year,
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            reason="The activity held no existencias at any time in the year.",
            decision_evidence=(
                InventoryClosingDecisionEvidence(
                    reference=statement,
                    role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                    content_digest="d" * 64,
                ),
            ),
            prior_evidence=(PriorClosingContinuityEvidence(reference=statement, content_digest="d" * 64),),
        ),
        document=InventoryLedgerDocument(ledgers=(fresh,)),
        ledger=fresh,
        actor="operator",
        source_command="ledger.inventory.closing-value.record",
        now=datetime(year + 1, 1, 10, tzinfo=UTC),
    )
    return fresh.model_copy(update={"closing_authority_record": record})
