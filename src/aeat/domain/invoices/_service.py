"""Service helpers for invoice catalogues and bidirectional transaction linking.

Exposes pure-function service operations over an
:class:`~aeat.domain.invoices.InvoiceCatalogue`: lookup
(:func:`find_invoice`, :func:`find_unmatched`), in-memory linking
(:func:`link_transaction`), reconciliation suggestions
(:func:`suggest_reconciliations`), bidirectional consistency checks
(:func:`verify_link_consistency`), and the persistence-level
bidirectional linker :func:`link_transaction_bidirectional` that
coordinates writes across the invoice and
:mod:`aeat.domain.transactions` catalogues with rollback semantics.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ...core.logging import get_logger
from ..transactions import (
    TransactionCatalogue,
    TransactionError,
)
from ..transactions import (
    link_invoice as _transactions_link_invoice,
)
from ._enums import InvoiceKind
from ._errors import (
    InvoiceLinkError,
    InvoiceLinkInconsistencyError,
    InvoiceNotFoundError,
)
from ._models import Invoice, InvoiceCatalogue

_LOGGER = get_logger(__name__)
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_DEFAULT_AMOUNT_TOLERANCE = Decimal("0.01")
_HEX_TRANSACTION_ID_LENGTH = 64


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

    invoice_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    amount_match: bool
    counterparty_match: bool
    score: Decimal

    @field_validator("score")
    @classmethod
    def _require_score_in_range(cls, value: Decimal) -> Decimal:
        if value < Decimal("0") or value > Decimal("1"):
            raise ValueError("score must be in the inclusive 0..1 range")
        return value


class LinkInconsistency(BaseModel):
    """Immutable record describing a one-sided link between the two catalogues.

    Attributes:
        invoice_id: Identifier of the invoice involved in the bad link.
        transaction_id: Identifier of the transaction involved.
        direction: Which side cites the other without being cited back.
    """

    model_config = _STRICT_FROZEN

    invoice_id: str
    transaction_id: str
    direction: Literal["invoice-only", "transaction-only"]


def find_invoice(catalogue: InvoiceCatalogue, invoice_id: str) -> Invoice | None:
    """Return one invoice from a catalogue if present.

    Args:
        catalogue: Source :class:`~aeat.domain.invoices.InvoiceCatalogue`.
        invoice_id: Stable invoice identifier to look up.

    Returns:
        The matching :class:`~aeat.domain.invoices.Invoice`, or ``None``
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
        catalogue: Source catalogue to filter.
        kind: Optional filter on :class:`InvoiceKind`.

    Returns:
        A tuple of invoices whose ``linked_transaction_ids`` is empty,
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
        A fresh immutable catalogue with the updated invoice. Duplicate
        links are idempotent: calling this helper with an already-linked
        transaction returns a value-equal catalogue rather than raising.

    Raises:
        :exc:`InvoiceNotFoundError`: If ``invoice_id`` is missing.
        :exc:`InvoiceLinkError`: If ``transaction_id`` is not a
            64-character lowercase hex digest.
    """
    invoice = _require_invoice(catalogue, invoice_id)
    normalized_tx = transaction_id.strip().lower()
    if len(normalized_tx) != _HEX_TRANSACTION_ID_LENGTH or any(
        char not in "0123456789abcdef" for char in normalized_tx
    ):
        raise InvoiceLinkError(f"transaction_id must be a 64-character lowercase hex digest: {transaction_id!r}")
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
            {**invoice.model_dump(mode="python"), "linked_transaction_ids": updated_ids}
        )
    except ValidationError as exc:
        raise InvoiceLinkError(f"invalid invoice link update for {invoice_id}") from exc
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
        invoices: Source invoice catalogue.
        transactions: Source transaction catalogue.
        amount_tolerance: Absolute tolerance applied to sign-aware amount
            comparisons; defaults to one cent.

    Returns:
        Deterministic tuple of suggestions sorted by
        ``(score desc, invoice_id asc, transaction_id asc)``.
    """
    unmatched_invoices = tuple(invoice for invoice in invoices.values() if not invoice.linked_transaction_ids)
    candidate_transactions = tuple(
        transaction for transaction in transactions.values() if transaction.invoice_id is None
    )
    suggestions: list[ReconciliationSuggestion] = []
    for invoice in unmatched_invoices:
        expected = invoice.grand_total if invoice.kind is InvoiceKind.ISSUED else -invoice.grand_total
        invoice_counterparty = invoice.counterparty_name.strip().lower()
        for transaction in candidate_transactions:
            amount_match = abs(transaction.raw.amount - expected) <= amount_tolerance
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
                )
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
        invoices: Source invoice catalogue.
        transactions: Source transaction catalogue.

    Returns:
        Deterministic tuple of inconsistencies sorted by
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
                        direction="invoice-only",
                    )
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
                    direction="transaction-only",
                )
            )
    inconsistencies.sort(key=lambda item: (item.invoice_id, item.transaction_id))
    if inconsistencies:
        _LOGGER.warning(
            "verify_link_consistency: %d one-sided link(s) detected",
            len(inconsistencies),
        )
    return tuple(inconsistencies)


def _write_bytes(path: Path, payload: bytes) -> None:
    """Default rollback writer: write ``payload`` to ``path`` verbatim."""
    path.write_bytes(payload)


def link_transaction_bidirectional(
    invoices_dir: Path,
    transactions_dir: Path,
    invoice_id: str,
    transaction_id: str,
    *,
    rollback_temp_writer: Callable[[Path, bytes], object] | None = None,
) -> tuple[InvoiceCatalogue, TransactionCatalogue]:
    """Update both catalogues so they cite each other.

    Loads both catalogues via their respective repositories, computes
    both updates in memory, then writes the invoice catalogue followed
    by the transaction catalogue. Both writes go through the
    encrypted-envelope substrate at FINANCIAL class. If the second
    write fails, the invoice envelope is rolled back to its prior
    byte-level ciphertext content; if the rollback itself fails, an
    :class:`InvoiceLinkInconsistencyError` is raised carrying both
    paths so an operator can repair the drift.

    Args:
        invoices_dir: Directory containing the invoice envelope file.
        transactions_dir: Directory containing the transaction envelope file.
        invoice_id: Invoice identifier to update.
        transaction_id: Transaction identifier to update.

    Returns:
        The freshly written pair of catalogues.

    Raises:
        :exc:`InvoiceNotFoundError`: If ``invoice_id`` is missing.
        :exc:`InvoiceLinkError`: If linking fails on either side for a
            typed reason.
        :exc:`InvoiceLinkInconsistencyError`: If both the transaction
            write and the invoice rollback fail; the two files are left
            in drifted state for manual repair.
    """
    from ..transactions._repository import TransactionCatalogueRepository
    from ._repository import InvoiceCatalogueRepository

    _LOGGER.debug("bidirectional link: invoice=%s transaction=%s", invoice_id, transaction_id)
    invoice_repo = InvoiceCatalogueRepository(store_dir=invoices_dir)
    transaction_repo = TransactionCatalogueRepository(store_dir=transactions_dir)
    invoices_path = invoice_repo.envelope_path
    transactions_path = transaction_repo.envelope_path

    invoice_catalogue = invoice_repo.load()
    transaction_catalogue = transaction_repo.load()
    prior_invoice_bytes = invoices_path.read_bytes() if invoices_path.exists() else None

    updated_invoices = link_transaction(invoice_catalogue, invoice_id, transaction_id)

    try:
        updated_transactions = _transactions_link_invoice(
            transaction_catalogue, _match_transaction_id(transaction_catalogue, transaction_id), invoice_id
        )
    except TransactionError as exc:
        raise InvoiceLinkError(f"could not link transaction {transaction_id} to invoice {invoice_id}") from exc

    invoice_repo.save(updated_invoices)
    _LOGGER.info("linked invoice=%s to transaction=%s", invoice_id, transaction_id)
    try:
        transaction_repo.save(updated_transactions)
    except TransactionError as exc:
        _rollback_invoice_file(
            invoices_path=invoices_path,
            transactions_path=transactions_path,
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            prior_bytes=prior_invoice_bytes,
            cause=exc,
            rollback_temp_writer=rollback_temp_writer,
        )
        raise InvoiceLinkError(f"transaction save failed for {transaction_id}; invoice file restored") from exc
    return updated_invoices, updated_transactions


def _rollback_invoice_file(
    *,
    invoices_path: Path,
    transactions_path: Path,
    invoice_id: str,
    transaction_id: str,
    prior_bytes: bytes | None,
    cause: BaseException,
    rollback_temp_writer: Callable[[Path, bytes], object] | None = None,
) -> None:
    """Best-effort restore the invoice catalogue after a transaction-write failure."""
    try:
        if prior_bytes is None:
            invoices_path.unlink(missing_ok=True)
        else:
            tmp = invoices_path.with_suffix(invoices_path.suffix + ".rollback.tmp")
            writer = rollback_temp_writer or _write_bytes
            writer(tmp, prior_bytes)
            os.replace(tmp, invoices_path)
            from ...core.locks import fsync_parent_dir

            fsync_parent_dir(invoices_path)
    except OSError as restore_exc:
        _LOGGER.error(
            "rollback failed invoice=%s transaction=%s; original transaction save error follows",
            invoice_id,
            transaction_id,
            exc_info=cause,
        )
        raise InvoiceLinkInconsistencyError(
            invoice_path=invoices_path,
            transactions_path=transactions_path,
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            message=(
                "transaction save failed and invoice rollback also failed; "
                "catalogues are inconsistent and require manual repair"
            ),
        ) from restore_exc
    _LOGGER.error(
        "rolled back invoice catalogue %s after transaction save failure",
        invoices_path,
        exc_info=cause,
    )


def _match_transaction_id(catalogue: TransactionCatalogue, transaction_id: str) -> str:
    """Return the canonical transaction ID from a catalogue, raising if absent."""
    if transaction_id in catalogue:
        return transaction_id
    normalized = transaction_id.strip().lower()
    if normalized in catalogue:
        return normalized
    raise InvoiceLinkError(f"transaction not found in catalogue: {transaction_id}")


def _replace_invoice(catalogue: InvoiceCatalogue, invoice: Invoice) -> InvoiceCatalogue:
    """Return a new catalogue with one invoice replaced."""
    updated = dict(catalogue.invoices)
    updated[invoice.invoice_id] = invoice
    return InvoiceCatalogue.model_validate({"invoices": updated})


def _require_invoice(catalogue: InvoiceCatalogue, invoice_id: str) -> Invoice:
    """Return one invoice or raise a typed not-found error."""
    invoice = catalogue.get(invoice_id)
    if invoice is None:
        raise InvoiceNotFoundError(f"invoice not found: {invoice_id}")
    return invoice
