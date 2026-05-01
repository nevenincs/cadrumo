"""Strict pydantic v2 records for the unified review queue.

Each per-kind model wraps the source record verbatim alongside the
unified queue fields (``item_id``, ``modelo``, ``severity``,
``summary``, ``drill_command``, ``since``). The :data:`ReviewItem`
discriminated union mirrors the canonical ``DivergencePayload``
pattern in ``aeat.application.sync._divergence`` (see ADR D1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.i18n import Translatable
from ...domain.invoices import Invoice
from ...domain.transactions import Transaction
from ..filing import FilingValidationFinding
from ..sync import DivergenceRecord
from ._enums import ReviewItemKind, ReviewSeverity

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class _ReviewItemBase(BaseModel):
    """Shared pydantic config + unified fields for every review item."""

    model_config = _STRICT_FROZEN

    item_id: str = Field(min_length=1)
    modelo: str | None
    severity: ReviewSeverity
    summary: Translatable
    drill_command: str = Field(min_length=1)
    since: datetime

    @field_validator("since")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        """Reject naive timestamps so sorting across sources is deterministic."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("since must be timezone-aware")
        return value


class TransactionReviewItem(_ReviewItemBase):
    """One pending transaction wrapped for the queue.

    Pending states (post-#237): ``NOT_YET_PROCESSED``,
    ``PROCESSED_UNCLASSIFIED``, ``FAILED_VALIDATION``. Severity is
    derived per state by ``_classify_transaction`` in ``_adapters``.
    """

    kind: Literal[ReviewItemKind.TRANSACTION] = ReviewItemKind.TRANSACTION
    source: Transaction


class InvoiceReviewItem(_ReviewItemBase):
    """One pending invoice (unmatched, disputed, or payment-pending)."""

    kind: Literal[ReviewItemKind.INVOICE] = ReviewItemKind.INVOICE
    source: Invoice


class DivergenceReviewItem(_ReviewItemBase):
    """One pending sync divergence record."""

    kind: Literal[ReviewItemKind.DIVERGENCE] = ReviewItemKind.DIVERGENCE
    source: DivergenceRecord


class FindingReviewItem(_ReviewItemBase):
    """One pending finding extracted from a filing draft.

    ``source`` is ``None`` for the placeholder row emitted when a
    draft has no findings but is in DRAFT or VALIDATED status (see
    ADR D2 drafts adapter rules). Otherwise it carries the verbatim
    :class:`FilingValidationFinding`.
    """

    kind: Literal[ReviewItemKind.FINDING] = ReviewItemKind.FINDING
    source: FilingValidationFinding | None
    draft_id: str = Field(min_length=1)
    draft_path: str = Field(min_length=1)


ReviewItem = Annotated[
    TransactionReviewItem | InvoiceReviewItem | DivergenceReviewItem | FindingReviewItem,
    Field(discriminator="kind"),
]
