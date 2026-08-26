"""Service helpers for invoice catalogues.

Exposes pure-function service operations over an
:class:`~cadrumo.domain.invoices.InvoiceCatalogue`: lookup
(:func:`find_invoice`, :func:`find_unmatched`), in-memory linking
(:func:`link_transaction`), reconciliation suggestions
(:func:`suggest_reconciliations`), and bidirectional consistency checks
(:func:`verify_link_consistency`). Operations that span both the invoice
catalogue and the :class:`TransactionCatalogue` accept each as an
independent argument. Persisted cross-catalogue workflows belong in
:mod:`cadrumo.application.invoices`.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import LinkInconsistencyDirection
from ...core.identity import InvoiceId, TransactionId
from ...core.logging import get_logger
from ..iva import InvoiceKind
from ..transactions import (
    TransactionCatalogue,
    TransactionDirection,
)
from ._models import Invoice, InvoiceCatalogue
from .errors import (
    InvoiceLinkError,
    InvoiceNotFoundError,
    InvoiceValidationError,
)

_LOGGER = get_logger(__name__)
#: Default closeness for proposing an invoice-to-transaction link.
#:
#: DELIBERATELY NOT :data:`~core.money.CENT`, despite carrying the same value.
#: CENT bounds rounding noise: it answers "could these two figures be the same
#: number, differently rounded". This answers something else -- "are these two
#: figures close enough that a human should be offered the link" -- which is a
#: matching heuristic, not an arithmetic invariant. It is a per-call default the
#: caller may widen; CENT is a quantum nobody may widen without changing what
#: rounding means. The two agreeing today is a coincidence of scale, and folding
#: this onto CENT would make a later loosening of link suggestions silently
#: loosen every rounding check in the codebase.
_DEFAULT_AMOUNT_TOLERANCE = Decimal("0.01")


class ReconciliationSuggestion(BaseModel):
    """Immutable suggestion emitted by the reconciliation heuristic.

    Attributes:
        invoice_id: Stable invoice identifier.
        transaction_id: Candidate transaction identifier.
        amount_match: Whether the sign-aware amount matches within tolerance.
        counterparty_match: Whether the counterparty name overlaps
            (case-insensitive substring match either direction).
        score: Confidence in the inclusive ``0..1`` range.
    """

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    transaction_id: TransactionId
    amount_match: bool
    counterparty_match: bool
    score: Decimal

    @field_validator("score")
    @classmethod
    def _require_score_in_range(cls, value: Decimal) -> Decimal:
        if not (0 <= value <= 1):
            raise InvoiceValidationError("score must be in the inclusive 0..1 range")
        return value


class LinkInconsistency(BaseModel):
    """Immutable record describing a one-sided link between the two catalogues.

    Attributes:
        invoice_id: Identifier of the invoice involved in the bad link.
        transaction_id: Identifier of the transaction involved.
        direction: Which side cites the other without being cited back, as a
            :class:`LinkInconsistencyDirection` member.
    """

    model_config = _STRICT_FROZEN

    # NOT core.identity.InvoiceId, deliberately: the TRANSACTION_ONLY branch
    # (verify_link_consistency) feeds this from transaction.invoice_id, which
    # is domain.transactions.Transaction's own bare `str | None` foreign key
    # -- unconstrained today, and this function's entire purpose is to
    # detect a transaction whose invoice_id does NOT resolve to a real
    # invoice. A stricter type here would make the diagnostic itself raise
    # on exactly the dangling reference it exists to report.
    invoice_id: str = Field(min_length=1)
    transaction_id: TransactionId
    direction: LinkInconsistencyDirection


def find_invoice(catalogue: InvoiceCatalogue, invoice_id: str) -> Invoice | None:
    """Return one invoice from a catalogue if present.

    Args:
        catalogue: Source :class:`~cadrumo.domain.invoices.InvoiceCatalogue`.
        invoice_id: Stable invoice identifier to look up.

    Returns:
        The matching :class:`~cadrumo.domain.invoices.Invoice`, or ``None``
        when absent.
    """
    return catalogue.get(invoice_id)


def find_unmatched(
    catalogue: InvoiceCatalogue,
    *,
    kind: InvoiceKind | None = None,
) -> tuple[Invoice, ...]:
    """Return the invoices that have no linked transactions yet.

    Args:
        catalogue: Source :class:`InvoiceCatalogue` to filter.
        kind: Optional filter on :class:`InvoiceKind`.

    Returns:
        A tuple of :class:`Invoice` objects whose ``linked_transaction_ids`` is empty,
        preserving insertion order. When ``kind`` is supplied, only
        invoices of that kind are returned.
    """
    return tuple(
        invoice
        for invoice in catalogue.values()
        if not invoice.linked_transaction_ids and (kind is None or invoice.kind is kind)
    )


def link_transaction(
    catalogue: InvoiceCatalogue,
    invoice_id: str,
    transaction_id: str,
) -> InvoiceCatalogue:
    """Return a new catalogue with ``transaction_id`` linked to ``invoice_id``.

    Args:
        catalogue: Source catalogue.
        invoice_id: Invoice identifier to update.
        transaction_id: Transaction identifier to append to the invoice's
            ``linked_transaction_ids`` tuple.

    Returns:
        A fresh immutable :class:`InvoiceCatalogue` with the updated invoice. Duplicate
        links are idempotent: calling this helper with an already-linked
        transaction returns a value-equal catalogue rather than raising.

    Raises:
        InvoiceLinkError: If ``transaction_id`` is not a 64-character
            lowercase hex digest.
    """
    invoice = _require_invoice(catalogue, invoice_id)
    normalized_tx = transaction_id.strip().lower()
    if len(normalized_tx) != 64 or any(char not in "0123456789abcdef" for char in normalized_tx):
        raise InvoiceLinkError(
            translated_message="errors.error.error_financial_invoices_invoice_link",
            context={"transaction_id": str(transaction_id), "hex_digest_shape_valid": False},
        )
    if normalized_tx in invoice.linked_transaction_ids:
        _LOGGER.debug(
            "link_transaction: transaction=%s already linked to invoice=%s; skipping",
            normalized_tx,
            invoice_id,
        )
        return catalogue
    updated_ids = (*invoice.linked_transaction_ids, normalized_tx)
    try:
        updated_invoice = Invoice.model_validate(
            {**invoice.model_dump(mode="python"), "linked_transaction_ids": updated_ids},
        )
    except ValidationError as exc:
        raise InvoiceLinkError(
            translated_message="errors.error.error_financial_invoices_invoice_link",
            context={"invoice_id": str(invoice_id), "link_update_error_type": type(exc).__name__},
        ) from exc
    return _replace_invoice(catalogue, updated_invoice)


def suggest_reconciliations(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    *,
    amount_tolerance: Decimal = _DEFAULT_AMOUNT_TOLERANCE,
) -> tuple[ReconciliationSuggestion, ...]:
    """Return auto-suggested invoice/transaction links sorted by score.

    Only unlinked invoices (empty ``linked_transaction_ids``) and
    transactions whose ``invoice_id`` is ``None`` are considered.
    Suggestions are emitted only when the amount matches within
    ``amount_tolerance``. Counterparty similarity acts as a score-boost
    (case-insensitive substring match) but is never sufficient on its
    own.

    Args:
        invoices: The :class:`InvoiceCatalogue` to match invoices from.
        transactions: Source :class:`TransactionCatalogue` to match transactions from.
        amount_tolerance: Absolute tolerance applied to sign-aware amount
            comparisons; defaults to one cent.

    Returns:
        Deterministic tuple of :class:`ReconciliationSuggestion` objects sorted by
        ``(score desc, invoice_id asc, transaction_id asc)``.
    """
    unmatched_invoices = tuple(invoice for invoice in invoices.values() if not invoice.linked_transaction_ids)
    candidate_transactions = tuple(
        transaction for transaction in transactions.values() if transaction.invoice_id is None
    )
    suggestions: list[ReconciliationSuggestion] = []
    for invoice in unmatched_invoices:
        # ``amount`` is a non-negative magnitude; flow is carried by
        # ``direction``. An ISSUED invoice
        # reconciles against an INCOMING transaction, a RECEIVED invoice
        # against an OUTGOING transaction, both matched on the magnitude
        # against the invoice grand total.
        expected_direction = (
            TransactionDirection.INCOMING if invoice.kind is InvoiceKind.ISSUED else TransactionDirection.OUTGOING
        )
        invoice_counterparty = invoice.counterparty_name.strip().lower()
        for transaction in candidate_transactions:
            if transaction.direction is not expected_direction:
                continue
            amount_match = abs(transaction.raw.amount - invoice.grand_total) <= amount_tolerance
            if not amount_match:
                continue
            tx_counterparty = transaction.raw.counterparty
            counterparty_match = False
            if tx_counterparty is not None and invoice_counterparty:
                tx_normalised = tx_counterparty.strip().lower()
                # ``bool(tx_normalised)`` guards against the empty-string case;
                # without it ``"" in invoice_counterparty`` returns True and
                # grants a false-positive 0.5 score boost.
                counterparty_match = bool(tx_normalised) and (
                    invoice_counterparty in tx_normalised or tx_normalised in invoice_counterparty
                )
            score = Decimal("0.5") * (1 if amount_match else 0)
            score += Decimal("0.5") * (1 if counterparty_match else 0)
            suggestions.append(
                ReconciliationSuggestion(
                    invoice_id=invoice.invoice_id,
                    transaction_id=transaction.transaction_id,
                    amount_match=amount_match,
                    counterparty_match=counterparty_match,
                    score=score,
                ),
            )
    suggestions.sort(key=lambda s: (-s.score, s.invoice_id, s.transaction_id))
    _LOGGER.debug("suggest_reconciliations: %d candidate(s)", len(suggestions))
    return tuple(suggestions)


def verify_link_consistency(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
) -> tuple[LinkInconsistency, ...]:
    """Return every one-sided link between the two catalogues.

    A link is ``invoice-only`` when an invoice cites a transaction that
    does not cite it back, and ``transaction-only`` when a transaction
    cites an invoice that does not cite it back.

    Args:
        invoices: The :class:`InvoiceCatalogue` to check links from.
        transactions: The :class:`TransactionCatalogue` to check links from.

    Returns:
        Deterministic tuple of :class:`LinkInconsistency` items sorted by
        ``(invoice_id, transaction_id)``.
    """
    inconsistencies: list[LinkInconsistency] = []
    for invoice in invoices.values():
        for tx_id in invoice.linked_transaction_ids:
            transaction = transactions.get(tx_id)
            if transaction is None or transaction.invoice_id != invoice.invoice_id:
                inconsistencies.append(
                    LinkInconsistency(
                        invoice_id=invoice.invoice_id,
                        transaction_id=tx_id,
                        direction=LinkInconsistencyDirection.INVOICE_ONLY,
                    ),
                )
    for transaction in transactions.values():
        if transaction.invoice_id is None:
            continue
        invoice = invoices.get(transaction.invoice_id)
        if invoice is None or transaction.transaction_id not in invoice.linked_transaction_ids:
            inconsistencies.append(
                LinkInconsistency(
                    invoice_id=transaction.invoice_id,
                    transaction_id=transaction.transaction_id,
                    direction=LinkInconsistencyDirection.TRANSACTION_ONLY,
                ),
            )
    inconsistencies.sort(key=lambda item: (item.invoice_id, item.transaction_id))
    if inconsistencies:
        _LOGGER.warning(
            "verify_link_consistency: %d one-sided link(s) detected",
            len(inconsistencies),
        )
    return tuple(inconsistencies)


def _replace_invoice(catalogue: InvoiceCatalogue, invoice: Invoice) -> InvoiceCatalogue:
    """Return a new catalogue with one invoice replaced."""
    updated = dict(catalogue.invoices)
    updated[invoice.invoice_id] = invoice
    return InvoiceCatalogue.model_validate({"invoices": updated})


def _require_invoice(catalogue: InvoiceCatalogue, invoice_id: str) -> Invoice:
    """Return one invoice or raise a typed not-found error."""
    invoice = catalogue.get(invoice_id)
    if invoice is None:
        raise InvoiceNotFoundError(
            translated_message="errors.error.error_financial_invoices_invoice_not_found",
            context={"invoice_id": str(invoice_id), "invoice_present": False},
        )
    return invoice
