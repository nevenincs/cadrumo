"""The findings that hold an activity's inventory rows back over its purchases' ledger statements.

A purchase of the book reaches casilla 0181 as acquisition cost. If a ledger row
books the same purchase, the row must be claimed so it is withheld from the
ledger expense casillas; a claim that does not stand, or a purchase that states
nothing about its ledger row while the year holds ledger expense rows, could
deduct the purchase twice or not at all. Either leaves the inventory rows
unresolved, which blocks verification, and never falls back to casilla 0183.
"""

from __future__ import annotations

from datetime import date

from ...domain.contribuyente.inventory.ledger_claims import InventoryClaimRefusal, unstated_purchases
from ...domain.contribuyente.inventory.records import InventoryLedger, InventoryLedgerDocument
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..inventory.movement_claim_checks import (
    InventoryClaimLedgerReads,
    claimable_transaction_facts,
    ledger_claim_refusals,
)

_EXPENSE_CLASSIFICATIONS = frozenset({BusinessClassification.BUSINESS, BusinessClassification.MIXED})

_CLAIM_REFUSAL_MESSAGES = {
    "claimed_transaction_missing": "names a ledger transaction that is not an active row of the ledger",
    "claimed_transaction_double_claim": (
        "names a ledger transaction that another inventory book or the activity-asset register also claims"
    ),
    "claimed_transaction_amount_mismatch": (
        "states a base, IVA or recargo that differs from the ledger transaction it claims"
    ),
    "claimed_transaction_substrate_missing": "names a ledger transaction that states no taxable base or IVA",
    "claimed_transaction_not_eur": "names a ledger transaction in a currency other than EUR",
}


def _row_date(row: Transaction) -> date:
    return row.operation_date or row.raw.value_date or row.raw.booked_date


def year_has_ledger_expense_rows(transactions: TransactionCatalogue, year: int) -> bool:
    """Whether the ledger holds an active business expense row dated in ``year``."""
    return any(
        row.lifecycle_state is TransactionLifecycleState.ACTIVE
        and row.direction is TransactionDirection.OUTGOING
        and row.business_classification in _EXPENSE_CLASSIFICATIONS
        and _row_date(row).year == year
        for row in transactions.values()
    )


def claim_refusal_message(refusal: InventoryClaimRefusal) -> str:
    """The technical account of one refused claim; it names the purchase and the row, never the activity."""
    movements = ", ".join(repr(movement_id) for movement_id in refusal.movement_ids)
    return (
        f"the {refusal.year} inventory purchase {movements} {_CLAIM_REFUSAL_MESSAGES[refusal.reason]} "
        f"(transaction {refusal.transaction_id!r})"
    )


CLAIM_REFUSAL_REMEDY = (
    "Correct the purchase's ledger transaction in the inventory book: name the ledger row that books exactly this "
    "purchase, with the same base, IVA and recargo, or state that no ledger row books it."
)

UNSTATED_PURCHASE_REMEDY = (
    "For each purchase of the inventory book, name the ledger row that books it, so the row leaves the ledger "
    "expenses and the purchase is declared once through the book, or state that no ledger row books it."
)


def inventory_claim_findings(
    document: InventoryLedgerDocument,
    ledgers: tuple[InventoryLedger, ...],
    *,
    filing_year: int,
    reads: InventoryClaimLedgerReads,
) -> tuple[tuple[str, str, str], ...]:
    """Every reason the book's purchases hold its rows back, as ``(state, message, remedy)``.

    Returns:
        One entry per refused claim, then one entry per book whose purchases state
        nothing while the year holds ledger expense rows; empty when every
        purchase's statement stands.
    """
    transactions = reads.transactions()
    facts = claimable_transaction_facts(transactions)
    assets = reads.asset_revisions()
    refused = tuple(
        ("purchase_ledger_claim_refused", claim_refusal_message(refusal), CLAIM_REFUSAL_REMEDY)
        for ledger in ledgers
        for refusal in ledger_claim_refusals(document, ledger, transactions=facts, assets=assets)
    )
    unstated = tuple(movement.movement_id for ledger in ledgers for movement in unstated_purchases(ledger))
    if not unstated or not year_has_ledger_expense_rows(transactions, filing_year):
        return refused
    listed = ", ".join(repr(movement_id) for movement_id in unstated)
    return (
        *refused,
        (
            "purchase_ledger_row_unstated",
            f"the {filing_year} inventory purchases {listed} state nothing about the ledger row that books them, "
            "and the ledger holds expense rows for the year",
            UNSTATED_PURCHASE_REMEDY,
        ),
    )


__all__ = [
    "CLAIM_REFUSAL_REMEDY",
    "UNSTATED_PURCHASE_REMEDY",
    "claim_refusal_message",
    "inventory_claim_findings",
    "year_has_ledger_expense_rows",
]
