"""Check a purchase's claim on a ledger transaction against the ledger and the asset register.

The same checks run when a claim is written and again when Modelo 100 is
calculated, so the row the expense resolver withholds and the acquisition the
inventory book adds to casilla 0181 stay the same money.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.identity.transaction_ids import TransactionId
from ...core.time.clock import now as clock_now_utc
from ...domain.contribuyente.inventory.closing_foundations import InventoryLedgerError
from ...domain.contribuyente.inventory.corrections import (
    InventoryChangeStamp,
    inventory_refusal_key,
    require_effective_purchase,
    state_movement_ledger_row,
)
from ...domain.contribuyente.inventory.ledger_claims import (
    ClaimedTransactionFacts,
    InventoryClaimRefusal,
    inventory_claim_refusals,
)
from ...domain.contribuyente.inventory.records import InventoryLedger, InventoryLedgerDocument, PurchaseLedgerRow
from ...domain.renta.actividad_asset.claims import current_revisions
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue


@dataclass(frozen=True, slots=True)
class InventoryClaimLedgerReads:
    """The two registers a claim is checked against, read when the claim is checked."""

    transactions: Callable[[], TransactionCatalogue]
    asset_revisions: Callable[[], tuple[ActivityAssetRevision, ...]]


def claimable_transaction_facts(transactions: TransactionCatalogue) -> dict[str, ClaimedTransactionFacts]:
    """The tax substrate of every active ledger row; an archived, stashed or split row is not in the ledger's totals."""
    return {
        row.transaction_id: ClaimedTransactionFacts(
            transaction_id=row.transaction_id,
            currency=row.raw.currency,
            taxable_base=row.taxable_base,
            iva_amount=row.iva_amount,
            recargo_amount=row.recargo_amount,
        )
        for row in transactions.values()
        if row.lifecycle_state is TransactionLifecycleState.ACTIVE
    }


def asset_claimed_transaction_ids(assets: tuple[ActivityAssetRevision, ...]) -> frozenset[str]:
    """The ledger rows the activity-asset register's current revisions name as acquisitions."""
    return frozenset(
        transaction_id
        for revision in current_revisions(assets).values()
        for transaction_id in revision.acquisition_transaction_ids
    )


def ledger_claim_refusals(
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    *,
    transactions: Mapping[str, ClaimedTransactionFacts],
    assets: tuple[ActivityAssetRevision, ...],
) -> tuple[InventoryClaimRefusal, ...]:
    """Every refused claim of one book."""
    return inventory_claim_refusals(
        document,
        ledger,
        transactions=transactions,
        asset_claimed=asset_claimed_transaction_ids(assets),
    )


def refusal_error(refusal: InventoryClaimRefusal) -> InventoryLedgerError:
    """The typed error a claim write refuses with, naming the purchase and the transaction."""
    return InventoryLedgerError(
        f"inventory purchase claim refused: {refusal.reason}",
        context={
            "actividad_id": refusal.actividad_id,
            "year": str(refusal.year),
            "movement_id": ", ".join(refusal.movement_ids),
            **refusal.facts,
        },
        translated_message=inventory_refusal_key(refusal.reason),
    )


def require_ledger_claims_stand(
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    *,
    reads: InventoryClaimLedgerReads,
) -> None:
    """Refuse a candidate book whose claims do not stand, with the first refusal's typed reason."""
    if not any(movement.claimed_transaction_id is not None for movement in ledger.period_movements):
        return
    refusals = ledger_claim_refusals(
        document,
        ledger,
        transactions=claimable_transaction_facts(reads.transactions()),
        assets=reads.asset_revisions(),
    )
    if refusals:
        raise refusal_error(refusals[0])


@dataclass(frozen=True, slots=True)
class InventoryClaimCandidate:
    """One ledger transaction a purchase may claim, as the ledger states it."""

    transaction_id: TransactionId
    booked_date: date
    counterparty: str | None
    description: str
    currency: str
    taxable_base: Decimal | None
    iva_amount: Decimal | None
    recargo_amount: Decimal | None


_PROBE_CORRECTION_ID = "claim-candidate-probe"
"""Names the throwaway change a candidate book is formed with; it is never stored."""


def claim_candidates(
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    *,
    movement_id: str,
    reads: InventoryClaimLedgerReads,
) -> tuple[InventoryClaimCandidate, ...]:
    """The ledger transactions one purchase may claim, in transaction order.

    Each active transaction is tried as the claim write tries it: the candidate book
    is formed by the same domain change, then checked by the same gate, and the
    transaction is kept only when the write would pass: no claim of that book is
    refused. A transaction the purchase already claims, or another book claims, is
    therefore not offered, and a book with another failing claim offers none.

    Raises:
        InventoryLedgerError: When the movement is not an effective purchase of the book.
    """
    require_effective_purchase(ledger, movement_id)
    catalogue = reads.transactions()
    facts = claimable_transaction_facts(catalogue)
    assets = reads.asset_revisions()
    stamp = InventoryChangeStamp(correction_id=_PROBE_CORRECTION_ID, recorded_at=clock_now_utc(), actor="probe")
    offered: list[InventoryClaimCandidate] = []
    for transaction_id in sorted(facts):
        try:
            candidate = state_movement_ledger_row(
                document,
                ledger,
                stamp=stamp,
                movement_id=movement_id,
                ledger_row=PurchaseLedgerRow.CLAIMED,
                claimed_transaction_id=transaction_id,
            )
        except InventoryLedgerError:
            continue
        if ledger_claim_refusals(document, candidate, transactions=facts, assets=assets):
            continue
        offered.append(_candidate(catalogue.transactions[transaction_id], facts[transaction_id]))
    return tuple(offered)


def _candidate(row: Transaction, facts: ClaimedTransactionFacts) -> InventoryClaimCandidate:
    return InventoryClaimCandidate(
        transaction_id=row.transaction_id,
        booked_date=row.raw.booked_date,
        counterparty=row.raw.counterparty,
        description=row.raw.description,
        currency=facts.currency,
        taxable_base=facts.taxable_base,
        iva_amount=facts.iva_amount,
        recargo_amount=facts.recargo_amount,
    )


__all__ = [
    "InventoryClaimCandidate",
    "InventoryClaimLedgerReads",
    "asset_claimed_transaction_ids",
    "claim_candidates",
    "claimable_transaction_facts",
    "ledger_claim_refusals",
    "refusal_error",
    "require_ledger_claims_stand",
]
