"""Injected doors to the registered evidence and attachment operations of one admitted profile.

Every door submits one typed request of its operation and returns that
operation's own public result, already correlated with its terminal receipt by
the host. The Records screens build requests from screen state and never read
an operation's result through any other channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

from pydantic import BaseModel

from ....application.ledger.attachment_mutation_operation import (
    LedgerAttachmentOperationResult,
    LedgerAttachRequest,
    LedgerDetachRequest,
)
from ....application.ledger.evidence_followup_contracts import (
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from ....application.ledger.evidence_ingestion_contracts import (
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
)
from ....application.ledger.evidence_mutation_operation import (
    LedgerEvidenceRemoveProjection,
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from ....application.ledger.evidence_read_operation import (
    LedgerEvidenceQueryProjection,
    LedgerEvidenceQueryRequest,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
)
from ....application.ledger.evidence_review_summaries import LedgerEvidenceReviewSummaryProjection

LEDGER_EVIDENCE_FILES_PAGE_SIZE: Final = 100
"""The most rows any evidence list table holds at once."""


class LedgerEvidenceFilesDoorV1[RequestT: BaseModel, ResultT: BaseModel](Protocol):
    """Injected door to one registered evidence operation for one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def __call__(self, request: RequestT) -> ResultT:
        """Submit one request and return its receipt-correlated public result."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerEvidenceFilesDoorsV1:
    """The twelve evidence and attachment doors the Records tools submit through."""

    query: LedgerEvidenceFilesDoorV1[LedgerEvidenceQueryRequest, LedgerEvidenceQueryProjection]
    view: LedgerEvidenceFilesDoorV1[LedgerEvidenceViewRequest, LedgerEvidenceViewProjection]
    update: LedgerEvidenceFilesDoorV1[LedgerEvidenceUpdateRequest, LedgerEvidenceUpdateProjection]
    remove: LedgerEvidenceFilesDoorV1[LedgerEvidenceRemoveRequest, LedgerEvidenceRemoveProjection]
    batch: LedgerEvidenceFilesDoorV1[LedgerEvidenceBatchRequest, LedgerEvidenceBatchProjection]
    attachment_queue: LedgerEvidenceFilesDoorV1[
        LedgerEvidenceAttachmentQueueRequest, LedgerEvidenceAttachmentQueueProjection
    ]
    attachment_view: LedgerEvidenceFilesDoorV1[
        LedgerEvidenceAttachmentViewRequest, LedgerEvidenceAttachmentViewProjection
    ]
    consent_list: LedgerEvidenceFilesDoorV1[LedgerEvidenceConsentListRequest, LedgerEvidenceConsentListProjection]
    review_view: LedgerEvidenceFilesDoorV1[LedgerEvidenceReviewViewRequest, LedgerEvidenceReviewViewProjection]
    review_summary: LedgerEvidenceFilesDoorV1[LedgerEvidenceReviewViewRequest, LedgerEvidenceReviewSummaryProjection]
    attach: LedgerEvidenceFilesDoorV1[LedgerAttachRequest, LedgerAttachmentOperationResult]
    detach: LedgerEvidenceFilesDoorV1[LedgerDetachRequest, LedgerAttachmentOperationResult]

    def __post_init__(self) -> None:
        """Refuse doors admitted for different profiles: one screen addresses one profile."""
        doors = (
            self.query,
            self.view,
            self.update,
            self.remove,
            self.batch,
            self.attachment_queue,
            self.attachment_view,
            self.consent_list,
            self.review_view,
            self.review_summary,
            self.attach,
            self.detach,
        )
        if len({door.profile_id for door in doors}) != 1:
            raise ValueError("evidence doors must all be admitted for one profile")

    @property
    def profile_id(self) -> UUID:
        """The one profile all twelve doors were admitted for."""
        return self.query.profile_id


__all__ = ["LEDGER_EVIDENCE_FILES_PAGE_SIZE", "LedgerEvidenceFilesDoorV1", "LedgerEvidenceFilesDoorsV1"]
