"""Synthetic in-memory doors behind the Records review reads.

``ledger.review`` answers a synthetic review queue and
``ledger.evidence.review.list`` answers synthetic drafts waiting for review.
Each door takes its operation's real request model and returns its real result
model, so the screens are driven through the validation the registered
operations publish. Each answer crosses a thread the way the runtime door's
transport does, and each call records whether a Textual worker made it. Every
value here is synthetic.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from textual.worker import NoActiveWorker, get_current_worker

from .....application.ledger.evidence_followup_contracts import (
    EvidenceReviewQueueRowProjection,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
)
from .....application.ledger.review_operation import (
    LedgerReviewProjection,
    LedgerReviewRequest,
    LedgerReviewRowProjection,
)
from .....application.ledger.workspace import LedgerWorkspaceProjectionV1
from .....application.review.filter import LedgerReviewStatus
from .....core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from .....core.errors.hierarchy import CadrumoError
from .....core.identity.transaction_ids import TransactionId

REVIEW_PROFILE_ID: Final = UUID("4dd00000-0000-4000-8000-0000000000d4")
_DRAFTED_AT: Final = datetime(2026, 3, 14, 9, 30, tzinfo=UTC)


def synthetic_review_id(index: int) -> TransactionId:
    """The 64-character transaction identity of the synthetic review row ``index``."""
    return f"{index:064x}"


def synthetic_review_row(
    index: int, *, status: LedgerReviewStatus = LedgerReviewStatus.PENDING
) -> LedgerReviewRowProjection:
    """One synthetic review row: a dated, described amount awaiting review."""
    return LedgerReviewRowProjection(
        id=synthetic_review_id(index),
        date=(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index % 365)).date().isoformat(),
        amount=f"{index + 1}.50",
        description=f"Compra sintética {index:05d}",
        status=status,
    )


def projection_review_rows(projection: LedgerWorkspaceProjectionV1) -> tuple[LedgerReviewRowProjection, ...]:
    """The review rows a workspace projection's own review identities describe."""
    entries = {entry.transaction_id: entry for entry in projection.entries}
    return tuple(
        LedgerReviewRowProjection(
            id=transaction_id,
            date=entries[transaction_id].date,
            amount=entries[transaction_id].amount,
            description=entries[transaction_id].description,
            status=LedgerReviewStatus(entries[transaction_id].review_status),
        )
        for transaction_id in projection.review_transaction_ids
    )


def synthetic_draft(
    index: int,
    *,
    reasons: tuple[ConfirmationBlockReason, ...] = (),
    advisories: tuple[ReviewAdvisoryKind, ...] = (),
) -> EvidenceReviewQueueRowProjection:
    """One synthetic draft waiting for review, with the blocking reasons and advisories given."""
    return EvidenceReviewQueueRowProjection(
        evidence_reference=f"{index:016x}",
        extractor="local-reader",
        drafted_at=_DRAFTED_AT + timedelta(minutes=index),
        blocking_count=len(reasons),
        reasons=reasons,
        advisory_count=len(advisories),
        advisories=advisories,
    )


def _in_worker() -> bool:
    try:
        get_current_worker()
    except NoActiveWorker:
        return False
    return True


class _RecordingDoor:
    """What every in-memory review door records: who called it and from which thread."""

    def __init__(self, profile_id: UUID, refusal: CadrumoError | None) -> None:
        self._profile_id = profile_id
        self.refusal = refusal
        """Raised instead of answering, as the runtime door raises a recorded refusal."""
        self.in_worker: list[bool] = []
        self.transport_threads: list[int] = []
        self.loop_threads: list[int] = []

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._profile_id

    def _record(self) -> None:
        self.in_worker.append(_in_worker())
        self.loop_threads.append(threading.get_ident())

    def _transported(self) -> None:
        self.transport_threads.append(threading.get_ident())
        if self.refusal is not None:
            raise self.refusal


class MemoryLedgerReviewDoor(_RecordingDoor):
    """``ledger.review`` answering a fixed synthetic queue."""

    def __init__(
        self,
        rows: Sequence[LedgerReviewRowProjection] = (),
        *,
        profile_id: UUID = REVIEW_PROFILE_ID,
        refusal: CadrumoError | None = None,
    ) -> None:
        super().__init__(profile_id, refusal)
        self.rows = tuple(rows)
        self.requests: list[LedgerReviewRequest] = []

    async def __call__(self, request: LedgerReviewRequest) -> LedgerReviewProjection:
        """Answer the queue from another thread, as the runtime transport does."""
        self._record()
        self.requests.append(request)
        return await asyncio.to_thread(self._answer, request)

    def _answer(self, request: LedgerReviewRequest) -> LedgerReviewProjection:
        self._transported()
        return LedgerReviewProjection(
            profile_id=request.profile_id,
            transaction_prefix=request.transaction_prefix,
            rows=self.rows,
            filters=(),
        )


class MemoryEvidenceReviewListDoor(_RecordingDoor):
    """``ledger.evidence.review.list`` answering fixed synthetic drafts."""

    def __init__(
        self,
        rows: Sequence[EvidenceReviewQueueRowProjection] = (),
        *,
        profile_id: UUID = REVIEW_PROFILE_ID,
        refusal: CadrumoError | None = None,
    ) -> None:
        super().__init__(profile_id, refusal)
        self.rows = tuple(sorted(rows, key=lambda row: row.evidence_reference))
        self.requests: list[LedgerEvidenceReviewListRequest] = []

    async def __call__(self, request: LedgerEvidenceReviewListRequest) -> LedgerEvidenceReviewListProjection:
        """Answer the drafts from another thread, as the runtime transport does."""
        self._record()
        self.requests.append(request)
        return await asyncio.to_thread(self._answer, request)

    def _answer(self, request: LedgerEvidenceReviewListRequest) -> LedgerEvidenceReviewListProjection:
        self._transported()
        return LedgerEvidenceReviewListProjection(profile_id=request.profile_id, rows=self.rows)


__all__ = [
    "REVIEW_PROFILE_ID",
    "MemoryEvidenceReviewListDoor",
    "MemoryLedgerReviewDoor",
    "projection_review_rows",
    "synthetic_draft",
    "synthetic_review_id",
    "synthetic_review_row",
]
