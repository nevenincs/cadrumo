"""Canonical workflow event and review-record contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import InvoiceId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.clock import now as utc_now
from ...core.time.utc import UtcInstant
from ...domain.contribuyente.normalise import normalise_key


class WorkflowEvent(BaseModel):
    """One operator-visible event emitted by a mutating workflow verb.

    Events are appended to :attr:`~application.workflow.state_models.WorkflowState.bucket_events`
    so the operator can audit which actions ran, when, and against which
    object. ``action`` names the verb (e.g. ``"profile.created"``); ``reason``
    carries a free-form human-readable annotation; ``bucket_id`` and
    ``object_id`` are optional pointers to the affected resource.
    """

    model_config = _STRICT_FROZEN

    action: str = Field(min_length=1)
    reason: str = ""
    bucket_id: BucketId | None = None
    object_id: str | None = None
    at: UtcInstant = Field(default_factory=utc_now)

    @field_validator("action", "reason")
    @classmethod
    def _trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("bucket_id", "object_id")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class LedgerReviewRecord(BaseModel):
    """Workflow attention annotation for one persisted transaction.

    Durable transaction facts are not stored here. Classification,
    category, business percentage, tax fields, evidence references,
    skip/final-disposition state, and corrections live on the
    bucket-scoped transaction catalogue.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    history: tuple[WorkflowEvent, ...] = ()
    updated_at: UtcInstant = Field(default_factory=utc_now)


class InvoiceReviewRecord(BaseModel):
    """Workflow annotations for one persisted invoice."""

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    fields: dict[str, str] = Field(default_factory=dict)
    history: tuple[WorkflowEvent, ...] = ()
    updated_at: UtcInstant = Field(default_factory=utc_now)

    @field_validator("fields")
    @classmethod
    def _normalise_fields(cls, value: dict[str, str]) -> dict[str, str]:
        return {normalise_key(str(key)): str(raw).strip() for key, raw in value.items()}


__all__ = ["InvoiceReviewRecord", "LedgerReviewRecord", "WorkflowEvent"]
