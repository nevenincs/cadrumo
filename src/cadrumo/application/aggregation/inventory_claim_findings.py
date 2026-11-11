"""The findings that hold an activity's inventory rows back over its purchases' ledger statements.

A purchase of the book reaches casilla 0181 as acquisition cost. If a ledger row
books the same purchase, the row must be claimed so it is withheld from the
ledger expense casillas; a claim that does not stand, or a purchase that states
nothing about its ledger row while its activity holds ledger expense rows in the
year, could deduct the purchase twice or not at all. Either leaves the inventory
rows unresolved, which blocks verification, and never falls back to casilla 0183.

A ledger row belongs to the activity it declares (``tipo_actividad``). A row that
declares none is unknown rather than any particular activity's, so it counts for
every book. A book is matched to those rows by the Modelo 036 activity code its
identifier states; a book whose identifier states none has no activity the rows
can be told apart by, so every row counts for it. With one book, every row counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...core.tipos_actividad import TipoActividad
from ...domain.contribuyente.inventory.ledger_claims import InventoryClaimRefusal, unstated_purchases
from ...domain.contribuyente.inventory.records import InventoryLedger, InventoryLedgerDocument
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
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


def year_has_ledger_expense_rows(
    transactions: TransactionCatalogue, year: int, *, activity: TipoActividad | None = None
) -> bool:
    """Whether the ledger holds an active business expense row dated in ``year``.

    With ``activity``, only a row that declares that activity or none counts: a row
    that declares another activity is that activity's, and an undeclared one could be.
    """
    return any(
        row.lifecycle_state is TransactionLifecycleState.ACTIVE
        and row.direction is TransactionDirection.OUTGOING
        and row.business_classification in _EXPENSE_CLASSIFICATIONS
        and _row_date(row).year == year
        and (activity is None or row.tipo_actividad in (None, activity))
        for row in transactions.values()
    )


def book_activity(ledger: InventoryLedger) -> TipoActividad | None:
    """The Modelo 036 activity a book's identifier states, or ``None`` when it states none."""
    try:
        return TipoActividad(ledger.actividad_id)
    except ValueError:
        return None


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


@dataclass(frozen=True, slots=True)
class InventoryClaimFinding:
    """One reason the book's purchases hold its rows back: its state, its words and the fact it states."""

    state: str
    message: str
    remedy: str
    fact: CalculationNoteFact


def _unstated_blocking(
    ledgers: tuple[InventoryLedger, ...], transactions: TransactionCatalogue, filing_year: int
) -> tuple[str, ...]:
    """The unstated purchases whose own activity holds ledger expense rows in the year."""
    blocking: list[str] = []
    for ledger in ledgers:
        movements = unstated_purchases(ledger)
        if not movements:
            continue
        activity = book_activity(ledger) if len(ledgers) > 1 else None
        if year_has_ledger_expense_rows(transactions, filing_year, activity=activity):
            blocking.extend(movement.movement_id for movement in movements)
    return tuple(blocking)


def inventory_claim_findings(
    document: InventoryLedgerDocument,
    ledgers: tuple[InventoryLedger, ...],
    *,
    filing_year: int,
    reads: InventoryClaimLedgerReads,
) -> tuple[InventoryClaimFinding, ...]:
    """Every reason the book's purchases hold its rows back.

    Returns:
        One finding per refused claim, then one for the purchases that state
        nothing about the ledger row that books them while their own activity holds
        ledger expense rows in the year; empty when every purchase's statement
        stands.
    """
    transactions = reads.transactions()
    facts = claimable_transaction_facts(transactions)
    assets = reads.asset_revisions()
    refused = tuple(
        InventoryClaimFinding(
            state="purchase_ledger_claim_refused",
            message=claim_refusal_message(refusal),
            remedy=CLAIM_REFUSAL_REMEDY,
            fact=CalculationNoteFact.of(
                CalculationNoteSentence.INVENTORY_PURCHASE_CLAIM_REFUSED,
                year=refusal.year,
                count=len(refusal.movement_ids),
            ),
        )
        for ledger in ledgers
        for refusal in ledger_claim_refusals(document, ledger, transactions=facts, assets=assets)
    )
    unstated = _unstated_blocking(ledgers, transactions, filing_year)
    if not unstated:
        return refused
    listed = ", ".join(repr(movement_id) for movement_id in unstated)
    return (
        *refused,
        InventoryClaimFinding(
            state="purchase_ledger_row_unstated",
            message=(
                f"the {filing_year} inventory purchases {listed} state nothing about the ledger row that books them, "
                "and the ledger holds expense rows for their activity in the year"
            ),
            remedy=UNSTATED_PURCHASE_REMEDY,
            fact=CalculationNoteFact.of(
                CalculationNoteSentence.INVENTORY_PURCHASE_LEDGER_ROW_UNSTATED,
                year=filing_year,
                count=len(unstated),
            ),
        ),
    )


__all__ = [
    "CLAIM_REFUSAL_REMEDY",
    "UNSTATED_PURCHASE_REMEDY",
    "InventoryClaimFinding",
    "book_activity",
    "claim_refusal_message",
    "inventory_claim_findings",
    "year_has_ledger_expense_rows",
]
