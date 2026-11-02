"""Which movement settles which invoice, as the ledger proposes a link.

A proposal is not a link: the person links, and a link is permanent, so each movement is offered
one best invoice and each invoice one movement. A candidate pairs an invoice no movement is linked
to with a movement linked to no invoice, in the flow the invoice is settled in, in the invoice's
currency, whose amount settles the invoice's total less its retención within the link tolerance.
Candidates rank by the invoice number found in the description, then the shortest issue-to-payment
gap, then the counterparty, then the amount. Equal candidates are ambiguous and the person chooses.

The flow, the settlement, the tolerance, the counterparty overlap and the movements a link can
take are the ones the link suggestion and the link writer use; this module adds the ranking.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final

from ..transactions.classification_effects import takes_changes, takes_invoice
from ..transactions.models import Transaction
from .models import Invoice
from .service import (
    INVOICE_MATCH_TOLERANCE,
    counterparties_overlap,
    invoice_settlement,
    invoice_settling_direction,
)

#: Paid up to this many days before the invoice's date still ranks by the gap; earlier ranks after
#: every payment made on or after issue.
EARLY_PAYMENT_DAYS: Final = 3
_LATE_RANK: Final = 1000
#: How far from an invoice's issue day the by-hand movement choice looks.
PICK_WINDOW_DAYS: Final = 10
#: A number shorter than this is not told apart from other digits in a description.
_MIN_REFERENCE_LENGTH: Final = 4

_NOT_COMPARED: Final = re.compile(r"[^A-Z0-9]+")

type Rank = tuple[int, int, int, Decimal]


def payment_date(transaction: Transaction) -> date:
    """Return the day a movement counts for: its value date, else the day it was booked."""
    return transaction.raw.value_date or transaction.raw.booked_date


def can_take_invoice(transaction: Transaction) -> bool:
    """Return whether a movement can be linked to an invoice at all; the link writer asks the same."""
    return takes_changes(transaction.lifecycle_state) and takes_invoice(transaction.direction)


def settles(transaction: Transaction, invoice: Invoice) -> bool:
    """Return whether ``transaction`` settles ``invoice`` by flow, currency and amount."""
    return (
        transaction.direction is invoice_settling_direction(invoice.kind)
        and transaction.raw.currency == invoice.currency
        and abs(transaction.raw.amount - invoice_settlement(invoice)) <= INVOICE_MATCH_TOLERANCE
    )


def _reference(text: str) -> str:
    return _NOT_COMPARED.sub("", text.upper())


def names_invoice_number(transaction: Transaction, invoice: Invoice) -> bool:
    """Return whether the description names the invoice's number, a too short one never counting."""
    number = _reference(invoice.invoice_number)
    return len(number) >= _MIN_REFERENCE_LENGTH and number in _reference(transaction.raw.description)


def days_after_issue(transaction: Transaction, invoice: Invoice) -> int:
    """Return the whole days from the invoice's date to the movement's, negative when paid first."""
    return (payment_date(transaction) - invoice.issued_at).days


@dataclass(frozen=True, slots=True)
class PaymentPair:
    """One movement and one invoice that settle each other, and the evidence it stands on."""

    transaction: Transaction
    invoice: Invoice
    number: bool
    gap: int
    counterparty: bool
    rank: Rank


@dataclass(frozen=True, slots=True)
class PaymentSuggestion:
    """A movement's best invoice with what competes with it."""

    pair: PaymentPair
    #: Another candidate ranks exactly as well: the person chooses.
    ambiguous: bool
    #: Pairs ranking exactly as well that share this movement or this invoice.
    ties: tuple[PaymentPair, ...] = field(default=())
    #: The movement's other candidates.
    others: tuple[PaymentPair, ...] = field(default=())


def _pair(transaction: Transaction, invoice: Invoice) -> PaymentPair | None:
    if not settles(transaction, invoice):
        return None
    gap = days_after_issue(transaction, invoice)
    number = names_invoice_number(transaction, invoice)
    counterparty = counterparties_overlap(invoice.counterparty_name, transaction.raw.counterparty)
    return PaymentPair(
        transaction=transaction,
        invoice=invoice,
        number=number,
        gap=gap,
        counterparty=counterparty,
        rank=(
            0 if number else 1,
            abs(gap) if gap >= -EARLY_PAYMENT_DAYS else _LATE_RANK - gap,
            0 if counterparty else 1,
            abs(transaction.raw.amount - invoice_settlement(invoice)),
        ),
    )


def _movement_id(pair: PaymentPair) -> str:
    return pair.transaction.transaction_id


def _invoice_id(pair: PaymentPair) -> str:
    return pair.invoice.invoice_id


def suggest_payments(
    transactions: Iterable[Transaction],
    invoices: Iterable[Invoice],
    *,
    staged: Mapping[str, str] | None = None,
) -> tuple[PaymentSuggestion, ...]:
    """Return one suggestion per movement that has one, newest movement first.

    ``staged`` maps a movement id to the invoice id a staged link already gives it: neither is
    offered to anything else.
    """
    taken = staged or {}
    taken_invoices = set(taken.values())
    open_movements = [
        transaction
        for transaction in transactions
        if can_take_invoice(transaction) and transaction.invoice_id is None and transaction.transaction_id not in taken
    ]
    unmatched = [
        invoice
        for invoice in invoices
        if not invoice.linked_transaction_ids and invoice.invoice_id not in taken_invoices
    ]
    pairs = [
        pair
        for invoice in unmatched
        for transaction in open_movements
        if (pair := _pair(transaction, invoice)) is not None
    ]
    pairs.sort(key=lambda pair: (pair.rank, _invoice_id(pair), _movement_id(pair)))
    used_movements: set[str] = set()
    used_invoices: set[str] = set()
    best: dict[str, PaymentSuggestion] = {}
    for pair in pairs:
        movement_id, invoice_id = _movement_id(pair), _invoice_id(pair)
        if movement_id in used_movements or invoice_id in used_invoices:
            continue
        ties = tuple(
            other
            for other in pairs
            if other is not pair
            and (_movement_id(other) == movement_id or _invoice_id(other) == invoice_id)
            and _movement_id(other) not in used_movements
            and _invoice_id(other) not in used_invoices
            and other.rank == pair.rank
        )
        used_movements.add(movement_id)
        used_invoices.add(invoice_id)
        best[movement_id] = PaymentSuggestion(
            pair=pair,
            ambiguous=bool(ties),
            ties=ties,
            others=tuple(other for other in pairs if other is not pair and _movement_id(other) == movement_id),
        )
    # A movement that ties for another's invoice points at the same choice.
    for suggestion in tuple(best.values()):
        for tie in suggestion.ties:
            tied_id = _movement_id(tie)
            if tied_id in best:
                continue
            best[tied_id] = PaymentSuggestion(
                pair=tie,
                ambiguous=True,
                ties=(suggestion.pair,),
                others=tuple(other for other in pairs if other is not tie and _movement_id(other) == tied_id),
            )
    newest_first = sorted(best.values(), key=lambda found: _movement_id(found.pair))
    newest_first.sort(key=lambda found: payment_date(found.pair.transaction), reverse=True)
    return tuple(newest_first)


@dataclass(frozen=True, slots=True)
class InvoiceChoice:
    """One invoice a movement may be linked to by hand."""

    invoice: Invoice
    settles: bool
    #: The movement a staged link already gives this invoice to, when not this one.
    staged_for: str | None
    #: How many other movements are already linked to it; partial payments make several.
    linked: int


def invoice_choices(
    transaction: Transaction,
    invoices: Iterable[Invoice],
    *,
    staged: Mapping[str, str] | None = None,
) -> tuple[InvoiceChoice, ...]:
    """Return the invoices of the movement's flow, newest first, with whether each settles it.

    ``staged`` maps a movement id to the invoice id a staged link gives it.
    """
    holders = {invoice_id: movement_id for movement_id, invoice_id in (staged or {}).items()}
    own = transaction.transaction_id
    chosen = [invoice for invoice in invoices if transaction.direction is invoice_settling_direction(invoice.kind)]
    chosen.sort(key=lambda invoice: invoice.invoice_id)
    chosen.sort(key=lambda invoice: invoice.issued_at, reverse=True)
    return tuple(
        InvoiceChoice(
            invoice=invoice,
            settles=settles(transaction, invoice),
            staged_for=None if holders.get(invoice.invoice_id) in (None, own) else holders[invoice.invoice_id],
            linked=sum(1 for linked in invoice.linked_transaction_ids if linked != own),
        )
        for invoice in chosen
    )


@dataclass(frozen=True, slots=True)
class MovementChoice:
    """One movement an invoice may be linked to by hand."""

    transaction: Transaction
    settles: bool


def movement_choices(
    invoice: Invoice,
    transactions: Iterable[Transaction],
    *,
    staged: Collection[str] = (),
) -> tuple[MovementChoice, ...]:
    """Return the open movements of the invoice's flow and currency paid near its issue day.

    Those that settle it come first, then by how near the amount is, then by how near the day.
    A movement a staged link already takes is not offered; ``staged`` holds those movement ids.
    """
    settlement = invoice_settlement(invoice)
    found = [
        transaction
        for transaction in transactions
        if can_take_invoice(transaction)
        and transaction.invoice_id is None
        and transaction.transaction_id not in staged
        and transaction.direction is invoice_settling_direction(invoice.kind)
        and transaction.raw.currency == invoice.currency
        and abs(days_after_issue(transaction, invoice)) <= PICK_WINDOW_DAYS
    ]
    found.sort(
        key=lambda transaction: (
            not settles(transaction, invoice),
            abs(transaction.raw.amount - settlement),
            abs(days_after_issue(transaction, invoice)),
            transaction.transaction_id,
        )
    )
    return tuple(
        MovementChoice(transaction=transaction, settles=settles(transaction, invoice)) for transaction in found
    )


__all__ = [
    "EARLY_PAYMENT_DAYS",
    "PICK_WINDOW_DAYS",
    "InvoiceChoice",
    "MovementChoice",
    "PaymentPair",
    "PaymentSuggestion",
    "can_take_invoice",
    "days_after_issue",
    "invoice_choices",
    "movement_choices",
    "names_invoice_number",
    "payment_date",
    "settles",
    "suggest_payments",
]
