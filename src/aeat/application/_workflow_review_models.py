"""Shared leaf models for the workflow and review packages.

:mod:`aeat.application.workflow` and :mod:`aeat.application.review` need each
other's pydantic models at runtime: :class:`WorkflowEvent` is instantiated by
review actions and embedded as a field type on
:class:`~aeat.application.review.InvoiceReviewRecord` and
:class:`~aeat.application.review.LedgerReviewRecord`; those two review records
are in turn embedded as field types on
:class:`~aeat.application.workflow.WorkflowState`. Neither side can import the
other's public facade without re-entering a partially-initialised package
during Python's import machinery (the facade `__init__` for either package
pulls in the other), and pydantic's eager field-type resolution makes the
dependency runtime-bound rather than annotation-only, so neither side of the
former direct cross-import was ``TYPE_CHECKING``-deferrable.

This module is the structural fix: it is a leaf with no dependency on either
:mod:`workflow` or :mod:`review`, so both packages import these four names
from here instead of from each other. :mod:`workflow` re-exports
:class:`WorkflowEvent` and :func:`utc_now` from its facade; :mod:`review`
re-exports :class:`InvoiceReviewRecord` and :class:`LedgerReviewRecord` from
its facade. Consumers outside these two packages are unaffected — they already
import through the public facades, which keep re-exporting the same names.

This module is private application-layer plumbing consumed only by
:mod:`aeat.application.workflow` and :mod:`aeat.application.review`; it is not
part of the :mod:`aeat.application` public surface and carries no `__all__`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core.identity import BucketId
from ..core.time import now as utc_now
from ..domain.contribuyente import normalise_key


class WorkflowEvent(BaseModel):
    """One operator-visible event emitted by a mutating workflow verb.

    Events are appended to :attr:`~aeat.application.workflow.WorkflowState.bucket_events`
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

    transaction_id: str = Field(min_length=1)
    history: tuple[WorkflowEvent, ...] = ()
    updated_at: datetime = Field(default_factory=utc_now)


class InvoiceReviewRecord(BaseModel):
    """Workflow annotations for one persisted invoice."""

    model_config = _STRICT_FROZEN

    invoice_id: str = Field(min_length=1)
    fields: dict[str, str] = Field(default_factory=dict)
    history: tuple[WorkflowEvent, ...] = ()
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("fields")
    @classmethod
    def _normalise_fields(cls, value: dict[str, str]) -> dict[str, str]:
        return {normalise_key(str(key)): str(raw).strip() for key, raw in value.items()}
