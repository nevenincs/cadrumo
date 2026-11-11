"""Check a purchase's claim on a ledger transaction against the ledger and the asset register.

The same checks run when a claim is written and again when Modelo 100 is
calculated, so the row the expense resolver withholds and the acquisition the
inventory book adds to casilla 0181 stay the same money.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ...domain.contribuyente.inventory.closing_foundations import InventoryLedgerError
from ...domain.contribuyente.inventory.corrections import inventory_refusal_key
from ...domain.contribuyente.inventory.ledger_claims import (
    ClaimedTransactionFacts,
    InventoryClaimRefusal,
    inventory_claim_refusals,
)
from ...domain.contribuyente.inventory.records import InventoryLedger, InventoryLedgerDocument
from ...domain.renta.actividad_asset.claims import current_revisions
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import TransactionCatalogue


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


__all__ = [
    "InventoryClaimLedgerReads",
    "asset_claimed_transaction_ids",
    "claimable_transaction_facts",
    "ledger_claim_refusals",
    "refusal_error",
    "require_ledger_claims_stand",
]
