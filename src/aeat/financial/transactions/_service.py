"""Service helpers for transaction catalogues."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from aeat.logging import get_logger

from ._enums import BusinessClassification
from ._errors import TransactionCatalogueError, TransactionNotFoundError, TransactionPersistenceError
from ._models import Transaction, TransactionCatalogue

_LOGGER = get_logger(__name__)


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
            handle.write(payload)
            tmp_path = Path(handle.name)
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
    classified_by: str,
) -> TransactionCatalogue:
    """Return a new catalogue with updated classification metadata.

    Args:
        catalogue: Source catalogue.
        transaction_id: Stable transaction identifier to update.
        classification: New business-classification state.
        business_pct: Business-use percentage for ``MIXED`` classifications.
        classified_by: Classifier source string: ``auto``, ``manual``, or
            ``rule:<rule-id>``.

    Returns:
        A fresh immutable catalogue with updated classification metadata.

    Raises:
        TransactionNotFoundError: If ``transaction_id`` is missing.
    """
    transaction = _require_transaction(catalogue, transaction_id)
    updated_transaction = _validate_transaction_update(
        {
            **transaction.model_dump(mode="python"),
            "business_classification": classification,
            "business_pct": business_pct,
            "classified_at": datetime.now(UTC),
            "classified_by": classified_by,
        },
        context=f"invalid classification update for transaction: {transaction_id}",
    )
    return _replace_transaction(catalogue, updated_transaction)


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
