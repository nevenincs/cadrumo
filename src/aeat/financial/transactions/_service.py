"""Service helpers for transaction catalogues."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from ...logging import get_logger
from ._enums import BusinessClassification
from ._errors import TransactionCatalogueError, TransactionNotFoundError, TransactionPersistenceError
from ._models import ClassificationHistoryEntry, Transaction, TransactionCatalogue

_LOGGER = get_logger(__name__)

_EntrySignature = tuple[BusinessClassification, Decimal | None, str, str]


def load_transactions(path: Path) -> TransactionCatalogue:
    """Load a transaction catalogue from one JSON file.

    Args:
        path: JSON file containing a serialized ``TransactionCatalogue``.

    Returns:
        The validated catalogue loaded from disk.

    Raises:
        TransactionPersistenceError: If the file cannot be read or validated.
    """
    target = path.resolve()
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise TransactionPersistenceError(f"unable to read transaction catalogue: {target}") from exc
    try:
        catalogue = TransactionCatalogue.model_validate_json(raw)
    except ValidationError as exc:
        raise TransactionPersistenceError(f"invalid transaction catalogue JSON: {target}") from exc
    _LOGGER.info("loaded %s transactions from %s", len(catalogue), target)
    return catalogue


def save_transactions(catalogue: TransactionCatalogue, path: Path) -> None:
    """Persist a transaction catalogue to disk atomically.

    Args:
        catalogue: Catalogue to persist.
        path: Destination JSON file.

    Raises:
        TransactionPersistenceError: If the write cannot be completed.
    """
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = catalogue.model_dump_json(indent=2)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f"{target.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
        os.replace(tmp_path, target)
    except OSError as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise TransactionPersistenceError(f"unable to write transaction catalogue: {target}") from exc
    _LOGGER.info("saved %s transactions to %s", len(catalogue), target)


def find_transaction(catalogue: TransactionCatalogue, transaction_id: str) -> Transaction | None:
    """Return one transaction from a catalogue if present.

    Args:
        catalogue: Catalogue to search.
        transaction_id: Stable transaction identifier.

    Returns:
        The matching transaction, or ``None`` when absent.
    """
    return catalogue.get(transaction_id)


def link_invoice(catalogue: TransactionCatalogue, transaction_id: str, invoice_id: str) -> TransactionCatalogue:
    """Return a new catalogue with ``invoice_id`` linked to one transaction.

    Args:
        catalogue: Source catalogue.
        transaction_id: Stable transaction identifier to update.
        invoice_id: Invoice foreign key to attach.

    Returns:
        A fresh immutable catalogue with the linked invoice.

    Raises:
        TransactionNotFoundError: If ``transaction_id`` is missing.
    """
    transaction = _require_transaction(catalogue, transaction_id)
    updated_transaction = _validate_transaction_update(
        {
            **transaction.model_dump(mode="python"),
            "invoice_id": invoice_id,
        },
        context=f"invalid invoice link for transaction: {transaction_id}",
    )
    return _replace_transaction(catalogue, updated_transaction)


def set_classification(
    catalogue: TransactionCatalogue,
    transaction_id: str,
    *,
    classification: BusinessClassification,
    business_pct: Decimal | None = None,
    category_id: str | None = None,
    notes: str | None = None,
    classified_by: str,
    reason: str = "",
) -> TransactionCatalogue:
    """Return a new catalogue with updated classification metadata.

    Appends a ``ClassificationHistoryEntry`` to the transaction's
    ``classification_history`` chain whenever the incoming decision
    differs (by state, percentage, ``classified_by``, or ``reason``)
    from the transaction's current head. Byte-identical re-classifies
    are skipped so rule engines can run idempotently without
    inflating history.

    Args:
        catalogue: Source catalogue.
        transaction_id: Stable transaction identifier to update.
        classification: New business-classification state.
        business_pct: Business-use percentage for ``MIXED`` classifications.
        category_id: Optional category ID for the transaction.
        notes: Optional notes or reasoning for the classification.
        classified_by: Classifier source string: ``auto``, ``manual``, or
            ``rule:<rule-id>``.
        reason: Free-text override justification; embedded in the
            history entry, not on the top-level transaction.

    Returns:
        A fresh immutable catalogue with updated classification metadata.

    Raises:
        TransactionNotFoundError: If ``transaction_id`` is missing.
    """
    transaction = _require_transaction(catalogue, transaction_id)
    now = datetime.now(UTC)
    normalised_reason = reason.strip()
    proposed_signature: _EntrySignature = (classification, business_pct, classified_by, normalised_reason)
    current_signature: _EntrySignature = (
        transaction.business_classification,
        transaction.business_pct,
        transaction.classified_by,
        transaction.classification_reason,
    )
    if proposed_signature == current_signature:
        history = transaction.classification_history
    else:
        prior_snapshot = snapshot_classification_state(transaction, fallback_at=now)
        history = (*transaction.classification_history, prior_snapshot)

    payload = {
        **transaction.model_dump(mode="python"),
        "business_classification": classification,
        "business_pct": business_pct,
        "classified_at": now,
        "classified_by": classified_by,
        "classification_reason": normalised_reason,
        "classification_history": history,
    }
    if category_id is not None:
        payload["category_id"] = category_id
    if notes is not None:
        payload["notes"] = notes

    updated_transaction = _validate_transaction_update(
        payload,
        context=f"invalid classification update for transaction: {transaction_id}",
    )
    return _replace_transaction(catalogue, updated_transaction)


def snapshot_classification_state(
    transaction: Transaction,
    *,
    fallback_at: datetime | None = None,
) -> ClassificationHistoryEntry:
    """Return a history entry capturing the transaction's current active state.

    When no explicit ``classified_at`` is present (the pipeline has
    never run against this transaction), fall back to the provenance
    ``ingested_at`` timestamp so the synthesised entry reflects when
    the transaction first entered the catalogue. This keeps the
    chain in chronological order. ``fallback_at`` is an optional final
    fallback for callers that want to cap the synthesised timestamp
    (e.g. ``set_classification`` uses ``datetime.now(UTC)``).
    """
    snapshot_at = transaction.classified_at or transaction.raw.provenance.ingested_at or fallback_at
    if snapshot_at is None:
        raise TransactionCatalogueError("cannot synthesise a classification snapshot without a timestamp")
    return ClassificationHistoryEntry(
        business_classification=transaction.business_classification,
        business_pct=transaction.business_pct,
        classified_at=snapshot_at,
        classified_by=transaction.classified_by,
        reason=transaction.classification_reason,
    )


def _replace_transaction(catalogue: TransactionCatalogue, transaction: Transaction) -> TransactionCatalogue:
    """Return a new catalogue with one transaction replaced."""
    updated = dict(catalogue.transactions)
    updated[transaction.transaction_id] = transaction
    return TransactionCatalogue.model_validate({"transactions": updated})


def _require_transaction(catalogue: TransactionCatalogue, transaction_id: str) -> Transaction:
    """Return one transaction or raise a typed not-found error."""
    transaction = catalogue.get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(f"transaction not found: {transaction_id}")
    return transaction


def _validate_transaction_update(payload: dict[str, object], *, context: str) -> Transaction:
    """Validate one transaction update payload and raise typed domain errors."""
    try:
        return Transaction.model_validate(payload)
    except ValidationError as exc:
        raise TransactionCatalogueError(context) from exc
