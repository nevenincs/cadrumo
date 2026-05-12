"""Application services for manual review annotations."""

from __future__ import annotations

from typing import Any

from ..workflow._models import WorkflowEvent, WorkflowState
from ..workflow._utils import _normalise_key, utc_now
from ._models import InvoiceReviewRecord, LedgerReviewRecord, LedgerSplit


def update_ledger_review(
    state: WorkflowState,
    transaction_id: str,
    *,
    fields: dict[str, str] | None = None,
    skipped: bool | None = None,
    split: LedgerSplit | None | object = None,
    clear_split: bool = False,
    action: str,
    reason: str = "",
) -> WorkflowState:
    """Return state with review metadata updated for one transaction."""

    reviews = dict(state.ledger_reviews)
    current = reviews.get(transaction_id, LedgerReviewRecord(transaction_id=transaction_id))
    if isinstance(current, dict):
        current = LedgerReviewRecord.model_validate(current)

    update: dict[str, Any] = {"updated_at": utc_now()}
    if fields:
        update["fields"] = {**current.fields, **{_normalise_key(key): raw for key, raw in fields.items()}}
    if skipped is not None:
        update["skipped"] = skipped
    if clear_split:
        update["split"] = None
    elif isinstance(split, LedgerSplit):
        update["split"] = split
    event = WorkflowEvent(action=action, reason=reason)
    update["history"] = (*current.history, event)
    reviews[transaction_id] = current.model_copy(update=update)
    return state.model_copy(update={"ledger_reviews": reviews, "updated_at": utc_now()})


def update_invoice_review(
    state: WorkflowState,
    invoice_id: str,
    *,
    fields: dict[str, str],
    action: str,
    reason: str = "",
) -> WorkflowState:
    """Return state with review metadata updated for one invoice."""

    reviews = dict(state.invoice_reviews)
    current = reviews.get(invoice_id, InvoiceReviewRecord(invoice_id=invoice_id))
    if isinstance(current, dict):
        current = InvoiceReviewRecord.model_validate(current)

    event = WorkflowEvent(action=action, reason=reason)
    reviews[invoice_id] = current.model_copy(
        update={
            "fields": {**current.fields, **{_normalise_key(key): raw for key, raw in fields.items()}},
            "history": (*current.history, event),
            "updated_at": utc_now(),
        }
    )
    return state.model_copy(update={"invoice_reviews": reviews, "updated_at": utc_now()})
