"""Purchase movements that claim the ledger transaction booking them, and the checks a claim must pass.

A claimed transaction is withheld from every Modelo 100 ledger expense
destination, because the book's purchase carries the same money into casilla
0181. The checks keep the withheld row and the book's acquisition the same
money: a claim that names no transaction, is claimed twice, or does not equal
the transaction's taxable base, IVA and recargo to the cent is refused.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from ....core.decimal.constants import MONEY_ZERO
from ....core.external_constants import DEFAULT_CURRENCY
from ....core.identity.transaction_ids import TransactionId
from .records import InventoryLedger, InventoryLedgerDocument, MovementKind, MovementRecord, PurchaseLedgerRow

InventoryClaimRefusalReason = Literal[
    "claimed_transaction_missing",
    "claimed_transaction_double_claim",
    "claimed_transaction_amount_mismatch",
    "claimed_transaction_substrate_missing",
    "claimed_transaction_not_eur",
]
"""Why a purchase's claim on a ledger transaction cannot stand."""


@dataclass(frozen=True, slots=True)
class InventoryPurchaseClaim:
    """One purchase movement of one book claiming one ledger transaction."""

    actividad_id: str
    year: int
    movement_id: str
    transaction_id: TransactionId


@dataclass(frozen=True, slots=True)
class ClaimedTransactionFacts:
    """The tax substrate of one ledger transaction a purchase may claim, in its own currency."""

    transaction_id: TransactionId
    currency: str
    taxable_base: Decimal | None
    iva_amount: Decimal | None
    recargo_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class InventoryClaimRefusal:
    """One refused claim, with the facts its sentence names."""

    reason: InventoryClaimRefusalReason
    actividad_id: str
    year: int
    transaction_id: TransactionId
    movement_ids: tuple[str, ...]
    facts: Mapping[str, str] = field(default_factory=dict[str, str])


def purchase_claims(ledger: InventoryLedger) -> tuple[InventoryPurchaseClaim, ...]:
    """Every effective purchase of one book that claims a ledger transaction, in movement order."""
    return tuple(
        InventoryPurchaseClaim(
            actividad_id=ledger.actividad_id,
            year=ledger.year,
            movement_id=movement.movement_id,
            transaction_id=movement.claimed_transaction_id,
        )
        for movement in ledger.period_movements
        if movement.claimed_transaction_id is not None
    )


def document_purchase_claims(document: InventoryLedgerDocument) -> tuple[InventoryPurchaseClaim, ...]:
    """Every claim of every book, retired books included, since a retired book's purchase still books its row."""
    return tuple(claim for ledger in document.ledgers for claim in purchase_claims(ledger))


def unstated_purchases(ledger: InventoryLedger) -> tuple[MovementRecord, ...]:
    """The effective purchases that state nothing about the ledger transaction booking them."""
    return tuple(
        movement
        for movement in ledger.period_movements
        if movement.kind is MovementKind.PURCHASE and movement.ledger_row is PurchaseLedgerRow.UNSTATED
    )


def _summed(movements: tuple[MovementRecord, ...]) -> tuple[Decimal, Decimal, Decimal]:
    base = iva = recargo = MONEY_ZERO
    for movement in movements:
        cost = movement.acquisition_cost
        if cost is None:
            continue
        base += cost.consideration_excluding_iva
        iva += cost.consideration_iva_amount
        recargo += cost.consideration_recargo_amount
    return base, iva, recargo


def _ledger_refusal(
    ledger: InventoryLedger,
    transaction_id: TransactionId,
    movements: tuple[MovementRecord, ...],
    *,
    transactions: Mapping[str, ClaimedTransactionFacts],
    owners: Mapping[str, frozenset[tuple[str, int]]],
    asset_claimed: frozenset[str],
) -> InventoryClaimRefusal | None:
    movement_ids = tuple(movement.movement_id for movement in movements)

    def refused(reason: InventoryClaimRefusalReason, **facts: str) -> InventoryClaimRefusal:
        return InventoryClaimRefusal(
            reason=reason,
            actividad_id=ledger.actividad_id,
            year=ledger.year,
            transaction_id=transaction_id,
            movement_ids=movement_ids,
            facts=facts,
        )

    if len(owners.get(transaction_id, frozenset())) > 1 or transaction_id in asset_claimed:
        return refused("claimed_transaction_double_claim")
    facts = transactions.get(transaction_id)
    if facts is None:
        return refused("claimed_transaction_missing")
    if facts.currency != DEFAULT_CURRENCY:
        return refused("claimed_transaction_not_eur", currency=facts.currency)
    if facts.taxable_base is None or facts.iva_amount is None:
        return refused("claimed_transaction_substrate_missing")
    stated = _summed(movements)
    booked = (facts.taxable_base, facts.iva_amount, facts.recargo_amount or MONEY_ZERO)
    if stated != booked:
        return refused(
            "claimed_transaction_amount_mismatch",
            book_base=str(stated[0]),
            book_iva=str(stated[1]),
            book_recargo=str(stated[2]),
            ledger_base=str(booked[0]),
            ledger_iva=str(booked[1]),
            ledger_recargo=str(booked[2]),
        )
    return None


def inventory_claim_refusals(
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    *,
    transactions: Mapping[str, ClaimedTransactionFacts],
    asset_claimed: frozenset[str],
) -> tuple[InventoryClaimRefusal, ...]:
    """Check every claim of one book against the ledger, the document's other books and the asset register.

    Each claimed transaction is checked once, over all of this book's purchases that
    claim it, so a multi-line invoice compares its summed lines. Each amount is
    compared separately to the cent; attributable cost components are not compared,
    because they are booked on their own documents.

    Returns:
        One refusal per claimed transaction that fails, in transaction order.
    """
    owners: dict[str, set[tuple[str, int]]] = {}
    # The book checked may be a candidate not yet in the document, so its own claims replace the stored ones.
    coordinate = (ledger.actividad_id, ledger.year)
    others = tuple(item for item in document.ledgers if (item.actividad_id, item.year) != coordinate)
    for claim in (*(claim for item in others for claim in purchase_claims(item)), *purchase_claims(ledger)):
        owners.setdefault(claim.transaction_id, set()).add((claim.actividad_id, claim.year))
    frozen_owners = {key: frozenset(value) for key, value in owners.items()}
    by_transaction: dict[str, list[MovementRecord]] = {}
    for movement in ledger.period_movements:
        if movement.claimed_transaction_id is not None:
            by_transaction.setdefault(movement.claimed_transaction_id, []).append(movement)
    return tuple(
        refusal
        for transaction_id in sorted(by_transaction)
        if (
            refusal := _ledger_refusal(
                ledger,
                transaction_id,
                tuple(by_transaction[transaction_id]),
                transactions=transactions,
                owners=frozen_owners,
                asset_claimed=asset_claimed,
            )
        )
        is not None
    )


__all__ = [
    "ClaimedTransactionFacts",
    "InventoryClaimRefusal",
    "InventoryClaimRefusalReason",
    "InventoryPurchaseClaim",
    "document_purchase_claims",
    "inventory_claim_refusals",
    "purchase_claims",
    "unstated_purchases",
]
