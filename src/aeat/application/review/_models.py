"""Strict pydantic v2 records for the unified review queue.

Each per-kind model wraps the source record verbatim alongside the
unified queue fields (``item_id``, ``modelo``, ``severity``,
``summary``, ``drill_command``, ``since``).

The :data:`ReviewItem` discriminated union uses a single
discriminator field (``kind``) to select the concrete model, and
pydantic enforces that discriminator at validation time.

Concrete models:

* :class:`TransactionReviewItem` — pending bank transactions.
* :class:`InvoiceReviewItem` — unmatched, disputed, or payment-pending invoices.
* :class:`FindingReviewItem` — pending findings on filing drafts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.i18n import Translatable as tr
from ...core.time._utc import validate_utc_aware
from ...domain.contribuyente import normalise_key
from ...domain.invoices import Invoice
from ...domain.transactions import Transaction
from ..filing import ModeloValidationFinding
from ..workflow._models import WorkflowEvent
from ..workflow._utils import utc_now
from ._enums import ReviewItemKind, ReviewSeverity


class _ReviewItemBase(BaseModel):
    """Shared pydantic config and unified fields for every review item.

    Attributes:
        item_id: Stable per-source identifier of the underlying record.
        modelo: Modelo code the item belongs to, or ``None`` when the
            source is not modelo-scoped (transactions, invoices).
        severity: One of :class:`ReviewSeverity`.
        summary: Multilingual one-line description.
        drill_command: Suggested ``aeat`` CLI command the operator can
            run to inspect or resolve the item.
        since: Timezone-aware UTC timestamp marking when the item became
            review-pending.
    """

    model_config = _STRICT_FROZEN

    item_id: str = Field(min_length=1)
    modelo: str | None
    severity: ReviewSeverity
    summary: tr
    drill_command: str = Field(min_length=1)
    since: datetime

    @field_validator("since")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        """Reject naive timestamps so cross-source sorting is deterministic."""
        return validate_utc_aware(value)


class TransactionReviewItem(_ReviewItemBase):
    """One pending bank transaction wrapped for the review queue.

    The pending states surfaced here are ``NOT_YET_PROCESSED``,
    ``PROCESSED_UNCLASSIFIED``, and ``FAILED_VALIDATION``. Severity is
    derived per state by the transaction-source adapter.

    Attributes:
        kind: Literal discriminator pinned to
            :attr:`ReviewItemKind.TRANSACTION`.
        source: The verbatim :class:`aeat.domain.transactions.Transaction`.
    """

    kind: Literal[ReviewItemKind.TRANSACTION] = ReviewItemKind.TRANSACTION
    source: Transaction


class InvoiceReviewItem(_ReviewItemBase):
    """One pending invoice (unmatched, disputed, or payment-pending).

    Attributes:
        kind: Literal discriminator pinned to
            :attr:`ReviewItemKind.INVOICE`.
        source: The verbatim :class:`aeat.domain.invoices.Invoice`.
    """

    kind: Literal[ReviewItemKind.INVOICE] = ReviewItemKind.INVOICE
    source: Invoice


class FindingReviewItem(_ReviewItemBase):
    """One pending finding extracted from a filing draft.

    ``source`` is ``None`` for the placeholder row emitted when a draft
    has no findings but is in a DRAFT or VALIDATED status. Otherwise it
    carries the verbatim
    :class:`aeat.application.filing.ModeloValidationFinding`.

    Attributes:
        kind: Literal discriminator pinned to
            :attr:`ReviewItemKind.FINDING`.
        source: The underlying finding, or ``None`` for a status
            placeholder row.
        draft_id: Identifier of the originating filing draft.
        draft_path: On-disk path of the originating filing draft.
    """

    kind: Literal[ReviewItemKind.FINDING] = ReviewItemKind.FINDING
    source: ModeloValidationFinding | None
    draft_id: str = Field(min_length=1)
    draft_path: str = Field(min_length=1)


ReviewItem = Annotated[
    TransactionReviewItem | InvoiceReviewItem | FindingReviewItem,
    Field(discriminator="kind"),
]
"""Discriminated union of every concrete review-queue item.

Pydantic dispatches to the correct concrete model using the ``kind``
field as the discriminator. Validate via
``TypeAdapter(ReviewItem).validate_python(...)`` or
``.validate_json(...)``.
"""


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
