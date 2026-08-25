"""Canonical workflow event and review-record contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import BucketId, InvoiceId, TransactionId
from ...core.time import now as utc_now
from ...core.time import validate_utc_aware
from ...domain.contribuyente import normalise_key


class WorkflowEvent(BaseModel):
    """One operator-visible event emitted by a mutating workflow verb.

    Events are appended to :attr:`~application.workflow.WorkflowState.bucket_events`
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
    at: datetime = Field(default_factory=utc_now)

    @field_validator("at")
    @classmethod
    def _instant_is_utc(cls, value: datetime) -> datetime:
        """Reject an event instant that is naive or not UTC.

        These records serialise as JSON, which preserves the offset, so the
        canonical contract is enforceable at the model boundary.
        """
        return validate_utc_aware(value)

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
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at")
    @classmethod
    def _instant_is_utc(cls, value: datetime) -> datetime:
        """Reject a review-update instant that is naive or not UTC.

        These records serialise as JSON, which preserves the offset, so the
        canonical contract is enforceable at the model boundary.
        """
        return validate_utc_aware(value)


class InvoiceReviewRecord(BaseModel):
    """Workflow annotations for one persisted invoice."""

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    fields: dict[str, str] = Field(default_factory=dict)
    history: tuple[WorkflowEvent, ...] = ()
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at")
    @classmethod
    def _instant_is_utc(cls, value: datetime) -> datetime:
        """Reject a review-update instant that is naive or not UTC.

        These records serialise as JSON, which preserves the offset, so the
        canonical contract is enforceable at the model boundary.
        """
        return validate_utc_aware(value)

    @field_validator("fields")
    @classmethod
    def _normalise_fields(cls, value: dict[str, str]) -> dict[str, str]:
        return {normalise_key(str(key)): str(raw).strip() for key, raw in value.items()}


__all__ = ["InvoiceReviewRecord", "LedgerReviewRecord", "WorkflowEvent", "utc_now"]
