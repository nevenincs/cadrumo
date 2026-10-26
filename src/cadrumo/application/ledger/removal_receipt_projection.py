"""Bounded wire projection shared by every ledger transaction-removal receipt.

Removing one transaction and resetting the whole catalogue run the same guards
and cascade: finalized filings that block the removal, drafts left stale by it,
evidence and attachments removed with it, and the audit events it wrote. Both
receipts publish those findings through the one projection defined here.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.buckets.event import BUCKET_ACTOR_LABEL_MAX_LENGTH
from .models import LedgerRemovalBlocker

MAX_LEDGER_REMOVAL_RECEIPT_ITEMS = 4096
MAX_LEDGER_REMOVAL_RECEIPT_REASON_LENGTH = 4096
_ReceiptIdentity = Annotated[str, Field(min_length=1, max_length=64)]
LedgerRemovalReceiptIdentities = Annotated[
    tuple[_ReceiptIdentity, ...], Field(max_length=MAX_LEDGER_REMOVAL_RECEIPT_ITEMS)
]


class LedgerRemovalBlockerProjection(BaseModel):
    """One bounded finalized filing reference or stale-draft advisory citing a removed transaction."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    revision_state: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)


_ReceiptBlockers = Annotated[
    tuple[LedgerRemovalBlockerProjection, ...],
    Field(max_length=MAX_LEDGER_REMOVAL_RECEIPT_ITEMS),
]


class LedgerRemovalReceiptProjection(BaseModel):
    """Bounded guard, cascade and audit findings that every removal receipt carries."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    dry_run: bool = False
    actor: str = Field(min_length=1, max_length=BUCKET_ACTOR_LABEL_MAX_LENGTH)
    reason: str = Field(max_length=MAX_LEDGER_REMOVAL_RECEIPT_REASON_LENGTH)
    cascaded_purchase_invoice_evidence_ids: LedgerRemovalReceiptIdentities = ()
    cascaded_attachment_ids: LedgerRemovalReceiptIdentities = ()
    blocking_modelo_references: _ReceiptBlockers = ()
    stale_draft_revision_references: _ReceiptBlockers = ()
    bucket_event_ids: LedgerRemovalReceiptIdentities = ()


def project_removal_blockers(rows: tuple[LedgerRemovalBlocker, ...]) -> tuple[LedgerRemovalBlockerProjection, ...]:
    """Copy every canonical blocker while enforcing the published item limit."""
    return tuple(
        LedgerRemovalBlockerProjection(
            work_unit_id=row.work_unit_id,
            calculation_revision_id=row.calculation_revision_id,
            revision_state=row.revision_state,
            modelo=row.modelo,
            filing_year=row.filing_year,
            period=row.period,
        )
        for row in rows
    )


__all__ = [
    "MAX_LEDGER_REMOVAL_RECEIPT_ITEMS",
    "MAX_LEDGER_REMOVAL_RECEIPT_REASON_LENGTH",
    "LedgerRemovalBlockerProjection",
    "LedgerRemovalReceiptIdentities",
    "LedgerRemovalReceiptProjection",
    "project_removal_blockers",
]
