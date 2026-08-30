"""Service helpers for transaction catalogues.

Pure functions over :class:`domain.transactions.TransactionCatalogue`:
each helper returns a fresh immutable catalogue rather than mutating
the input. The module brokers the classification/percentage coupling
rules and history-chain bookkeeping that callers must not implement
ad-hoc.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from pydantic import ValidationError

from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...core.logging import get_logger
from ...core.time import now as _utc_now
from .enums import BusinessClassification
from .errors import TransactionCatalogueError, TransactionNotFoundError
from .models import ClassificationHistoryEntry, Transaction, TransactionCatalogue

_LOGGER = get_logger(__name__)

_DEFAULT_MANUAL_CONFIDENCE = Decimal("1.0")

_EntrySignature = tuple[BusinessClassification, Decimal | None, str, str, str | None, str, Decimal | None]


def find_transaction(catalogue: TransactionCatalogue, transaction_id: str) -> Transaction | None:
    """Return one transaction from a catalogue if present.

    Args:
        catalogue: The :class:`TransactionCatalogue` to search.
        transaction_id: Stable transaction identifier.

    Returns:
        The matching :class:`Transaction`, or ``None`` when absent.
    """
    return catalogue.get(transaction_id)


def link_invoice(catalogue: TransactionCatalogue, transaction_id: str, invoice_id: str) -> TransactionCatalogue:
    """Return a new catalogue with ``invoice_id`` linked to one transaction.

    Args:
        catalogue: Source catalogue.
        transaction_id: Stable transaction identifier to update.
        invoice_id: Invoice foreign key to attach.

    Returns:
        A fresh immutable :class:`TransactionCatalogue` with the linked invoice.
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
    confidence: Decimal | None = None,
) -> TransactionCatalogue:
    """Return a new catalogue with updated classification metadata.

    Appends a ``ClassificationHistoryEntry`` to the transaction's
    ``classification_history`` chain whenever the incoming decision
    differs (by state, percentage, ``classified_by``, ``reason``,
    ``category_id``, ``notes``, or ``confidence``) from the transaction's
    current head. Byte-identical re-classifies are skipped so rule engines
    can run idempotently without inflating history.

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
        confidence: Caller-supplied decision confidence in the inclusive
            ``[0, 1]`` range. When omitted, manual decisions default
            to ``Decimal("1.0")`` and all other classifier paths default
            to ``None``.

    Returns:
        A fresh :class:`TransactionCatalogue` with updated classification metadata.

    """
    transaction = _require_transaction(catalogue, transaction_id)
    now = _utc_now()
    normalised_reason = reason.strip()
    # Strip classified_by here so the idempotence signature below matches the
    # value the model will store (the field validator also strips, so a raw
    # "  manual  " parameter would otherwise force a spurious history entry).
    normalised_classified_by = classified_by.strip()
    resolved_confidence = _resolve_confidence(
        classified_by=normalised_classified_by,
        confidence=confidence,
    )
    proposed_signature: _EntrySignature = (
        classification,
        business_pct,
        normalised_classified_by,
        normalised_reason,
        category_id if category_id is not None else transaction.category_id,
        notes if notes is not None else transaction.notes,
        resolved_confidence,
    )
    current_signature: _EntrySignature = (
        transaction.business_classification,
        transaction.business_pct,
        transaction.classified_by,
        transaction.classification_reason,
        transaction.category_id,
        transaction.notes,
        transaction.classification_confidence,
    )
    if proposed_signature == current_signature:
        _LOGGER.debug(
            "set_classification: skipping idempotent re-classify for transaction %s (classification=%s)",
            transaction_id,
            classification.value,
        )
        history = transaction.classification_history
    else:
        _LOGGER.info(
            "set_classification: updating transaction %s classification=%s classified_by=%s",
            transaction_id,
            classification.value,
            normalised_classified_by,
        )
        prior_snapshot = snapshot_classification_state(transaction, fallback_at=now)
        history = (*transaction.classification_history, prior_snapshot)

    payload = {
        **transaction.model_dump(mode="python"),
        "business_classification": classification,
        "business_pct": business_pct,
        "classified_at": now,
        "classified_by": normalised_classified_by,
        "classification_reason": normalised_reason,
        "classification_confidence": resolved_confidence,
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


def _resolve_confidence(*, classified_by: str, confidence: Decimal | None) -> Decimal | None:
    """Return the confidence value to persist for one classification event.

    Args:
        classified_by: Classifier source string.
        confidence: Caller-supplied confidence.

    Returns:
        The caller-supplied confidence when non-None; otherwise
        ``Decimal("1.0")`` for manual decisions and ``None`` for every
        other classifier source.
    """
    if confidence is not None:
        return confidence
    if classified_by == CLASSIFIED_BY_MANUAL:
        return _DEFAULT_MANUAL_CONFIDENCE
    return None


def snapshot_classification_state(
    transaction: Transaction,
    *,
    fallback_at: datetime | None = None,
) -> ClassificationHistoryEntry:
    """Return a :class:`ClassificationHistoryEntry` capturing the transaction's current active state.

    When no explicit ``classified_at`` is present (the pipeline has
    never run against this transaction), fall back to the provenance
    ``ingested_at`` timestamp so the synthesised entry reflects when
    the transaction first entered the catalogue. This keeps the
    chain in chronological order. ``fallback_at`` is an optional final
    fallback for callers that want to cap the synthesised timestamp
    (e.g. ``set_classification`` uses the canonical clock helper).
    """
    ingested_at = getattr(transaction.raw.provenance, "ingested_at", None)
    snapshot_at = transaction.classified_at or ingested_at or fallback_at
    if snapshot_at is None:
        raise TransactionCatalogueError("cannot synthesise a classification snapshot without a timestamp")
    return ClassificationHistoryEntry(
        business_classification=transaction.business_classification,
        business_pct=transaction.business_pct,
        classified_at=snapshot_at,
        classified_by=transaction.classified_by,
        reason=transaction.classification_reason,
        category_id=transaction.category_id,
        notes=transaction.notes,
        confidence=transaction.classification_confidence,
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


def _validate_transaction_update(payload: Mapping[str, object], *, context: str) -> Transaction:
    """Validate one transaction update payload and raise typed domain errors."""
    try:
        return Transaction.model_validate(payload)
    except ValidationError as exc:
        _LOGGER.error("transaction update validation failed: %s", context, exc_info=True)
        raise TransactionCatalogueError(context) from exc
