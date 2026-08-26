"""Application services for manual review annotations.

:func:`update_ledger_review` and :func:`update_invoice_review` return updated
:class:`~cadrumo.application.workflow.WorkflowState` instances by appending
:class:`~cadrumo.application.workflow.WorkflowEvent` history to the relevant
:class:`LedgerReviewRecord` or :class:`InvoiceReviewRecord`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.contribuyente import normalise_key
from ..workflow.review_models import WorkflowEvent, utc_now
from ._models import InvoiceReviewRecord, LedgerReviewRecord
from .errors import ReviewError

if TYPE_CHECKING:
    from cadrumo.application.workflow.state_models import WorkflowState


def update_ledger_review(
    state: WorkflowState,
    transaction_id: str,
    *,
    fields: dict[str, str] | None = None,
    skipped: bool | None = None,
    split: object = None,
    clear_split: bool = False,
    action: str,
    reason: str = "",
) -> WorkflowState:
    """Return a :class:`WorkflowState` with workflow attention history for one transaction."""
    if fields:
        raise ReviewError(
            translated_message="errors.error.error_review",
            context={"field_class": "durable_ledger_field", "writable_through_review": False},
        )
    if skipped is not None:
        raise ReviewError(
            translated_message="errors.error.error_review",
            context={"field": "skipped", "canonical_writer": "transaction_classification"},
        )
    if split is not None or clear_split:
        raise ReviewError(
            translated_message="errors.error.error_review",
            context={"field": "split", "canonical_writer": "transaction_business_pct"},
        )

    reviews = dict(state.ledger_reviews)
    current = reviews.get(transaction_id, LedgerReviewRecord(transaction_id=transaction_id))
    if isinstance(current, dict):
        current = LedgerReviewRecord.model_validate(current)

    event = WorkflowEvent(action=action, reason=reason)
    update = {"updated_at": utc_now(), "history": (*current.history, event)}
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
    """Return the updated :class:`WorkflowState` with review metadata for one invoice applied."""
    reviews = dict(state.invoice_reviews)
    current = reviews.get(invoice_id, InvoiceReviewRecord(invoice_id=invoice_id))
    if isinstance(current, dict):
        current = InvoiceReviewRecord.model_validate(current)

    event = WorkflowEvent(action=action, reason=reason)
    reviews[invoice_id] = current.model_copy(
        update={
            "fields": {**current.fields, **{normalise_key(key): raw for key, raw in fields.items()}},
            "history": (*current.history, event),
            "updated_at": utc_now(),
        },
    )
    return state.model_copy(update={"invoice_reviews": reviews, "updated_at": utc_now()})
